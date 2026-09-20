from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest import skipUnless
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from crawlee import Request
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase

from operations.models import (
    OperationalControl,
    OperationalControlCode,
    WorkerHeartbeat,
    WorkerState,
)
from prospector.observation_contracts import ObservationTarget, make_handoff_key

from observer.contracts import (
    AttemptOutcome,
    ObservationOutcome,
    ObservationTrigger,
)
from observer.django_inbox import drain_crawlee_inbox
from observer.django_runtime import (
    LEASE_EXPIRED_FAILURE,
    claim_observations,
    execute_claim,
    recover_expired_observations,
    schedule_due_observations,
)
from observer.django_store import absorb_observation_target
from observer.errors import ObserverStateConflictError
from observer.runtime_contracts import AcquisitionResult, ObserverRuntimePolicy
from observer.testing import FakeAcquisition

from .models import (
    Observation,
    ObservationAttempt,
    ObservationSeries,
    ObserverHandoff,
)


class FakeDrainQueue:
    def __init__(self, requests=(), *, fail_mark_once=False):
        self.pending = list(requests)
        self.handled = []
        self.reclaimed = []
        self.fail_mark_once = fail_mark_once
        self.fetch_count = 0

    async def fetch_next_request(self):
        self.fetch_count += 1
        if not self.pending:
            return None
        return self.pending.pop(0)

    async def mark_request_as_handled(self, request):
        if self.fail_mark_once:
            self.fail_mark_once = False
            raise RuntimeError("simulated acknowledgement failure")
        self.handled.append(request)
        return object()

    async def reclaim_request(self, request, *, forefront=False):
        self.reclaimed.append(request)
        if forefront:
            self.pending.insert(0, request)
        else:
            self.pending.append(request)
        return object()


def crawlee_request_for(target: ObservationTarget):
    return Request.from_url(
        target.locator,
        unique_key=target.handoff_key,
        label="makolo-observation",
        user_data={
            "makolo": {
                "contract_version": target.contract_version,
                "target_key": target.target_key,
                "handoff_key": target.handoff_key,
                "handoff_generation": target.handoff_generation,
                "locator": target.locator,
                "kind": target.kind,
                "requested_at": target.requested_at.isoformat(),
                "observation_hints": dict(target.observation_hints),
            }
        },
    )


class ObserverRuntimeTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 20, 4, 0, tzinfo=timezone.utc)
        self.policy = ObserverRuntimePolicy(
            lease_seconds=60,
            recovery_retry_seconds=30,
        )
        self.target_key = "web_url:v1:" + ("a" * 64)

    def target(self, generation=1):
        return ObservationTarget(
            handoff_key=make_handoff_key(
                target_key=self.target_key,
                handoff_generation=generation,
            ),
            target_key=self.target_key,
            handoff_generation=generation,
            locator="https://example.test/resource",
            kind="web_url",
            requested_at=self.now + timedelta(seconds=generation),
            observation_hints={},
        )

    def absorb(self, generation=1):
        target = self.target(generation)
        handoff, _created = absorb_observation_target(
            target,
            absorbed_at=self.now + timedelta(seconds=10 + generation),
        )
        return handoff

    def observed_fake(self, observed_at):
        return FakeAcquisition(
            lambda claim: AcquisitionResult(
                outcome=ObservationOutcome.OBSERVED,
                observed_at=observed_at,
                final_locator=claim.locator,
                response_status=204,
            )
        )

    def test_inbox_ack_failure_replays_idempotently(self):
        target = self.target(1)
        request = crawlee_request_for(target)
        queue = FakeDrainQueue([request], fail_mark_once=True)

        with self.assertRaises(RuntimeError):
            async_to_sync(drain_crawlee_inbox)(queue, limit=1)

        self.assertEqual(ObserverHandoff.objects.count(), 1)
        self.assertEqual(len(queue.reclaimed), 1)

        stats = async_to_sync(drain_crawlee_inbox)(queue, limit=1)

        self.assertEqual(stats.absorbed, 0)
        self.assertEqual(stats.replayed, 1)
        self.assertEqual(len(queue.handled), 1)
        self.assertEqual(ObserverHandoff.objects.count(), 1)

    def test_malformed_inbox_item_is_reclaimed_without_durable_handoff(self):
        target = self.target(1)
        request = Request.from_url(
            target.locator,
            unique_key=target.handoff_key,
            label="unexpected",
            user_data={"makolo": {}},
        )
        queue = FakeDrainQueue([request])

        with self.assertRaises(Exception):
            async_to_sync(drain_crawlee_inbox)(queue, limit=1)

        self.assertEqual(ObserverHandoff.objects.count(), 0)
        self.assertEqual(len(queue.reclaimed), 1)

    def test_explicit_generations_are_scheduled_sequentially(self):
        first_handoff = self.absorb(1)
        second_handoff = self.absorb(2)

        scheduled = schedule_due_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
            limit=10,
        )

        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0].source_handoff, first_handoff)
        claims = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=21),
            limit=10,
        )
        self.assertEqual(len(claims), 1)
        execute_claim(
            claims[0],
            acquisition=self.observed_fake(
                self.now + timedelta(seconds=22)
            ),
            policy=self.policy,
            now=self.now + timedelta(seconds=21),
            completed_at=self.now + timedelta(seconds=23),
        )

        next_scheduled = schedule_due_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=24),
            limit=10,
        )

        self.assertEqual(len(next_scheduled), 1)
        self.assertEqual(
            next_scheduled[0].source_handoff,
            second_handoff,
        )
        self.assertEqual(
            next_scheduled[0].trigger,
            ObservationTrigger.HANDOFF.value,
        )

    def test_pending_generation_wins_over_due_watch(self):
        first_handoff = self.absorb(1)
        scheduled = schedule_due_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )
        claim = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=21),
        )[0]
        execute_claim(
            claim,
            acquisition=self.observed_fake(
                self.now + timedelta(seconds=22)
            ),
            policy=self.policy,
            now=self.now + timedelta(seconds=21),
            completed_at=self.now + timedelta(seconds=23),
        )
        series = scheduled[0].series
        series.watch_due_at = self.now + timedelta(seconds=30)
        series.save(update_fields=["watch_due_at", "updated_at"])
        second_handoff = self.absorb(2)

        next_scheduled = schedule_due_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=31),
        )

        self.assertEqual(len(next_scheduled), 1)
        self.assertEqual(next_scheduled[0].source_handoff, second_handoff)
        self.assertEqual(
            next_scheduled[0].trigger,
            ObservationTrigger.HANDOFF.value,
        )
        series.refresh_from_db()
        self.assertIsNone(series.watch_due_at)
        self.assertEqual(first_handoff.target_key, second_handoff.target_key)

    def test_failed_acquisition_schedules_retry_not_watch(self):
        self.absorb(1)
        schedule_due_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )
        claim = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=21),
        )[0]
        retry_at = self.now + timedelta(seconds=40)
        fake = FakeAcquisition(
            lambda _claim: AcquisitionResult(
                outcome=ObservationOutcome.FAILED,
                observed_at=self.now + timedelta(seconds=22),
                failure_code="fake.transient",
                retry_at=retry_at,
            )
        )
        failed = execute_claim(
            claim,
            acquisition=fake,
            policy=self.policy,
            now=self.now + timedelta(seconds=21),
            completed_at=self.now + timedelta(seconds=23),
        )

        self.assertEqual(failed.outcome, ObservationOutcome.FAILED.value)
        failed.series.refresh_from_db()
        self.assertEqual(failed.series.retry_due_at, retry_at)
        self.assertEqual(
            schedule_due_observations(
                policy=self.policy,
                now=self.now + timedelta(seconds=39),
            ),
            (),
        )

        retry = schedule_due_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=41),
        )
        self.assertEqual(len(retry), 1)
        self.assertEqual(
            retry[0].trigger,
            ObservationTrigger.RETRY.value,
        )

    def test_expired_lease_finalizes_attempt_and_rejects_old_claim(self):
        self.absorb(1)
        observation = schedule_due_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )[0]
        claim = claim_observations(
            worker_id="dead-worker",
            policy=self.policy,
            now=self.now + timedelta(seconds=21),
        )[0]
        ObservationAttempt.objects.create(
            observation=observation,
            ordinal=1,
            strategy="direct_http",
            lifecycle="open",
            started_at=self.now + timedelta(seconds=22),
            requested_locator=observation.requested_locator,
        )
        observation.lease_expires_at = self.now + timedelta(seconds=23)
        observation.save(update_fields=["lease_expires_at", "updated_at"])

        recovered = recover_expired_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=24),
        )

        self.assertEqual(recovered, 1)
        observation.refresh_from_db()
        self.assertEqual(observation.outcome, ObservationOutcome.FAILED.value)
        self.assertEqual(observation.failure_code, LEASE_EXPIRED_FAILURE)
        attempt = observation.attempts.get()
        self.assertEqual(attempt.outcome, AttemptOutcome.INTERRUPTED.value)
        observation.series.refresh_from_db()
        self.assertIsNotNone(observation.series.retry_due_at)
        with self.assertRaises(ObserverStateConflictError):
            execute_claim(
                claim,
                acquisition=self.observed_fake(
                    self.now + timedelta(seconds=25)
                ),
                policy=self.policy,
                now=self.now + timedelta(seconds=25),
                completed_at=self.now + timedelta(seconds=26),
            )

    def test_claim_is_not_given_to_second_worker(self):
        self.absorb(1)
        schedule_due_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )

        first = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=21),
        )
        second = claim_observations(
            worker_id="worker-b",
            policy=self.policy,
            now=self.now + timedelta(seconds=21),
        )

        self.assertEqual(len(first), 1)
        self.assertEqual(second, ())

    def test_worker_kill_switch_prevents_queue_access(self):
        OperationalControl.objects.filter(
            pk=OperationalControlCode.OBSERVER
        ).update(is_enabled=False)
        stdout = StringIO()
        with patch(
            "observer.django_app.management.commands.observer_worker.RequestQueue.open",
            new_callable=AsyncMock,
        ) as open_queue:
            call_command(
                "observer_worker",
                "--queue-name",
                "observer-test",
                "--instance-id",
                "observer-kill-switch-test",
                "--once",
                stdout=stdout,
            )

        open_queue.assert_not_awaited()
        heartbeat = WorkerHeartbeat.objects.get(
            worker_name="observer",
            instance_id="observer-kill-switch-test",
        )
        self.assertEqual(heartbeat.state, WorkerState.STOPPED)
        self.assertEqual(
            heartbeat.metadata["last_stats"]["operational_control"],
            "disabled",
        )

    def test_worker_one_shot_records_heartbeat_without_acquisition(self):
        queue = FakeDrainQueue()
        stdout = StringIO()
        with patch(
            "observer.django_app.management.commands.observer_worker.RequestQueue.open",
            new=AsyncMock(return_value=queue),
        ):
            call_command(
                "observer_worker",
                "--queue-name",
                "observer-test",
                "--instance-id",
                "observer-once-test",
                "--once",
                stdout=stdout,
            )

        heartbeat = WorkerHeartbeat.objects.get(
            worker_name="observer",
            instance_id="observer-once-test",
        )
        self.assertEqual(heartbeat.state, WorkerState.STOPPED)
        self.assertEqual(
            heartbeat.metadata["acquisition"],
            "unconfigured_lot2",
        )
        self.assertEqual(
            heartbeat.metadata["last_stats"]["acquisition"],
            "not_configured",
        )


@skipUnless(
    connection.vendor == "postgresql",
    "Observer concurrent claim contract requires PostgreSQL",
)
class ObserverPostgreSQLConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.now = datetime(2026, 9, 20, 4, 0, tzinfo=timezone.utc)
        self.policy = ObserverRuntimePolicy(lease_seconds=60)
        target_key = "web_url:v1:" + ("b" * 64)
        target = ObservationTarget(
            handoff_key=make_handoff_key(
                target_key=target_key,
                handoff_generation=1,
            ),
            target_key=target_key,
            handoff_generation=1,
            locator="https://example.test/concurrent",
            kind="web_url",
            requested_at=self.now,
            observation_hints={},
        )
        absorb_observation_target(target, absorbed_at=self.now)
        schedule_due_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=1),
        )

    def test_concurrent_workers_never_claim_same_observation(self):
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def run(worker_id):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                claims = claim_observations(
                    worker_id=worker_id,
                    policy=self.policy,
                    now=self.now + timedelta(seconds=2),
                    limit=1,
                )
                results.append(claims)
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=run, args=("worker-a",)),
            threading.Thread(target=run, args=("worker-b",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(sum(len(item) for item in results), 1)
        observation = Observation.objects.get()
        self.assertIsNotNone(observation.claim_token)
        self.assertIn(observation.claimed_by, {"worker-a", "worker-b"})
