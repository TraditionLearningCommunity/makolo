from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest import skipUnless
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from crawlee import Request
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase

from operations.models import WorkerState
from prospector.observation_contracts import ObservationTarget, make_handoff_key

from observer.contracts import (
    AttemptOutcome,
    ObservationOutcome,
    ObservationTrigger,
)
from observer.django_inbox import InboxDrainStats, drain_crawlee_inbox
from observer.django_runtime import (
    LEASE_EXPIRED_FAILURE,
    claim_observations,
    execute_claim,
    observation_backlog,
    recover_expired_observations,
)
from observer.django_store import absorb_observation_target
from observer.errors import ObserverStateConflictError
from observer.runtime_contracts import (
    AcquisitionResult,
    ObservationBacklog,
    ObserverRuntimePolicy,
)
from observer.testing import FakeAcquisition

from .models import (
    Observation,
    ObservationAttempt,
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

    def observation_for_claim(self, claim):
        return Observation.objects.select_related(
            "series",
            "source_handoff",
        ).get(observation_ref=claim.observation_ref)

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

    def test_backlog_never_creates_observation_before_claim(self):
        self.absorb(1)

        backlog = observation_backlog(
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )

        self.assertEqual(backlog.pending_handoffs, 1)
        self.assertEqual(backlog.open_observations, 0)
        self.assertEqual(Observation.objects.count(), 0)

    def test_explicit_generations_start_sequentially(self):
        first_handoff = self.absorb(1)
        second_handoff = self.absorb(2)

        first_claims = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
            limit=10,
        )

        self.assertEqual(len(first_claims), 1)
        first = self.observation_for_claim(first_claims[0])
        self.assertEqual(first.source_handoff, first_handoff)
        self.assertEqual(first.trigger, ObservationTrigger.HANDOFF.value)
        backlog_while_first_is_open = observation_backlog(
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )
        self.assertEqual(backlog_while_first_is_open.pending_handoffs, 1)
        self.assertEqual(backlog_while_first_is_open.open_observations, 1)
        execute_claim(
            first_claims[0],
            acquisition=self.observed_fake(
                self.now + timedelta(seconds=21)
            ),
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
            completed_at=self.now + timedelta(seconds=22),
        )

        second_claims = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=23),
            limit=10,
        )

        self.assertEqual(len(second_claims), 1)
        second = self.observation_for_claim(second_claims[0])
        self.assertEqual(second.source_handoff, second_handoff)
        self.assertEqual(second.trigger, ObservationTrigger.HANDOFF.value)

    def test_historical_handoffs_do_not_starve_new_generation(self):
        for generation in range(1, 5):
            self.absorb(generation)
            claims = claim_observations(
                worker_id="worker-a",
                policy=self.policy,
                now=self.now + timedelta(seconds=20 + generation * 10),
                limit=1,
            )
            self.assertEqual(len(claims), 1)
            execute_claim(
                claims[0],
                acquisition=self.observed_fake(
                    self.now + timedelta(seconds=21 + generation * 10)
                ),
                policy=self.policy,
                now=self.now + timedelta(seconds=20 + generation * 10),
                completed_at=self.now + timedelta(seconds=22 + generation * 10),
            )

        newest = self.absorb(5)
        claims = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=100),
            limit=1,
        )

        self.assertEqual(len(claims), 1)
        observation = self.observation_for_claim(claims[0])
        self.assertEqual(observation.source_handoff, newest)

    def test_pending_generation_wins_over_due_watch(self):
        first_handoff = self.absorb(1)
        first_claim = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )[0]
        first = self.observation_for_claim(first_claim)
        execute_claim(
            first_claim,
            acquisition=self.observed_fake(
                self.now + timedelta(seconds=21)
            ),
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
            completed_at=self.now + timedelta(seconds=22),
        )
        series = first.series
        series.watch_due_at = self.now + timedelta(seconds=30)
        series.save(update_fields=["watch_due_at", "updated_at"])
        second_handoff = self.absorb(2)

        claim = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=31),
        )[0]

        observation = self.observation_for_claim(claim)
        self.assertEqual(observation.source_handoff, second_handoff)
        self.assertEqual(
            observation.trigger,
            ObservationTrigger.HANDOFF.value,
        )
        series.refresh_from_db()
        self.assertIsNone(series.watch_due_at)
        self.assertEqual(first_handoff.target_key, second_handoff.target_key)

    def test_failed_acquisition_schedules_retry_not_watch(self):
        self.absorb(1)
        claim = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )[0]
        retry_at = self.now + timedelta(seconds=40)
        fake = FakeAcquisition(
            lambda _claim: AcquisitionResult(
                outcome=ObservationOutcome.FAILED,
                observed_at=self.now + timedelta(seconds=21),
                failure_code="fake.transient",
                retry_at=retry_at,
            )
        )
        failed = execute_claim(
            claim,
            acquisition=fake,
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
            completed_at=self.now + timedelta(seconds=22),
        )

        self.assertEqual(failed.outcome, ObservationOutcome.FAILED.value)
        failed.series.refresh_from_db()
        self.assertEqual(failed.series.retry_due_at, retry_at)
        self.assertEqual(
            claim_observations(
                worker_id="worker-a",
                policy=self.policy,
                now=self.now + timedelta(seconds=39),
            ),
            (),
        )

        retry_claims = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=41),
        )
        self.assertEqual(len(retry_claims), 1)
        retry_observation = self.observation_for_claim(retry_claims[0])
        self.assertEqual(
            retry_observation.trigger,
            ObservationTrigger.RETRY.value,
        )

    def test_unexpected_acquisition_exception_is_durable_and_re_raised(self):
        self.absorb(1)
        claim = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )[0]

        def explode(_claim):
            raise RuntimeError("adapter bug")

        with self.assertRaisesRegex(RuntimeError, "adapter bug"):
            execute_claim(
                claim,
                acquisition=FakeAcquisition(explode),
                policy=self.policy,
                now=self.now + timedelta(seconds=20),
                completed_at=self.now + timedelta(seconds=22),
            )

        observation = self.observation_for_claim(claim)
        self.assertEqual(
            observation.outcome,
            ObservationOutcome.FAILED.value,
        )
        self.assertEqual(
            observation.failure_code,
            "runtime.acquisition_exception",
        )
        self.assertIsNotNone(observation.retry_at)
        attempt = observation.attempts.get()
        self.assertEqual(attempt.outcome, AttemptOutcome.FAILED.value)

    def test_expired_lease_finalizes_attempt_and_rejects_old_claim(self):
        self.absorb(1)
        claim = claim_observations(
            worker_id="dead-worker",
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )[0]
        observation = self.observation_for_claim(claim)
        ObservationAttempt.objects.create(
            observation=observation,
            ordinal=1,
            strategy="direct_http",
            lifecycle="open",
            started_at=self.now + timedelta(seconds=21),
            requested_locator=observation.requested_locator,
        )
        observation.lease_expires_at = self.now + timedelta(seconds=22)
        observation.save(update_fields=["lease_expires_at", "updated_at"])

        recovered = recover_expired_observations(
            policy=self.policy,
            now=self.now + timedelta(seconds=23),
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
                    self.now + timedelta(seconds=24)
                ),
                policy=self.policy,
                now=self.now + timedelta(seconds=24),
                completed_at=self.now + timedelta(seconds=25),
            )

    def test_claim_is_not_given_to_second_worker(self):
        self.absorb(1)

        first = claim_observations(
            worker_id="worker-a",
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )
        second = claim_observations(
            worker_id="worker-b",
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
        )

        self.assertEqual(len(first), 1)
        self.assertEqual(second, ())

    def test_worker_kill_switch_prevents_queue_access(self):
        stdout = StringIO()
        command_path = (
            "observer.django_app.management.commands.observer_worker"
        )
        with (
            patch(
                f"{command_path}.is_operational_control_enabled",
                return_value=False,
            ),
            patch(
                f"{command_path}.RequestQueue.open",
                new_callable=AsyncMock,
            ) as open_queue,
            patch(
                f"{command_path}.Command._heartbeat",
                new_callable=AsyncMock,
            ) as heartbeat,
        ):
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
        self.assertEqual(heartbeat.await_count, 1)
        kwargs = heartbeat.await_args.kwargs
        self.assertEqual(kwargs["state"], WorkerState.STOPPED)
        self.assertEqual(
            kwargs["metadata"]["last_stats"]["operational_control"],
            "disabled",
        )

    def test_worker_remains_control_plane_without_explicit_http_opt_in(self):
        queue = FakeDrainQueue()
        stdout = StringIO()
        command_path = (
            "observer.django_app.management.commands.observer_worker"
        )
        backlog = ObservationBacklog(
            pending_handoffs=2,
            due_retries=1,
            due_watches=0,
            open_observations=0,
        )
        with (
            patch(
                f"{command_path}.is_operational_control_enabled",
                return_value=True,
            ),
            patch(
                f"{command_path}.RequestQueue.open",
                new=AsyncMock(return_value=queue),
            ),
            patch(
                f"{command_path}.drain_crawlee_inbox",
                new=AsyncMock(
                    return_value=InboxDrainStats(
                        fetched=0,
                        absorbed=0,
                        replayed=0,
                    )
                ),
            ),
            patch(
                f"{command_path}.recover_expired_observations",
                return_value=0,
            ),
            patch(
                f"{command_path}.claim_observations",
            ) as claim,
            patch(
                f"{command_path}.execute_claim",
            ) as execute,
            patch(
                f"{command_path}.observation_backlog_all_profiles",
                return_value=backlog,
            ),
            patch(
                f"{command_path}.build_direct_http_acquisition",
            ) as build_acquisition,
            patch(
                f"{command_path}.build_browser_render_acquisition",
            ) as build_browser_acquisition,
            patch(
                f"{command_path}.Command._heartbeat",
                new_callable=AsyncMock,
            ) as heartbeat,
        ):
            call_command(
                "observer_worker",
                "--queue-name",
                "observer-test",
                "--instance-id",
                "observer-control-plane-test",
                "--once",
                stdout=stdout,
            )

        build_acquisition.assert_not_called()
        build_browser_acquisition.assert_not_called()
        claim.assert_not_called()
        execute.assert_not_called()
        final_kwargs = heartbeat.await_args.kwargs
        self.assertEqual(final_kwargs["state"], WorkerState.STOPPED)
        self.assertEqual(
            final_kwargs["metadata"]["last_stats"]["acquisition"],
            "disabled",
        )

    def test_worker_one_shot_claims_and_executes_direct_http_work(self):
        queue = FakeDrainQueue()
        stdout = StringIO()
        command_path = (
            "observer.django_app.management.commands.observer_worker"
        )
        backlog = ObservationBacklog(
            pending_handoffs=2,
            due_retries=1,
            due_watches=0,
            open_observations=0,
        )
        fake_claim = object()
        fake_observation = type(
            "FinalizedObservation",
            (),
            {"outcome": ObservationOutcome.OBSERVED.value},
        )()
        fake_acquisition = object()
        with (
            patch(
                f"{command_path}.is_operational_control_enabled",
                return_value=True,
            ),
            patch(
                f"{command_path}.RequestQueue.open",
                new=AsyncMock(return_value=queue),
            ) as open_queue,
            patch(
                f"{command_path}.drain_crawlee_inbox",
                new=AsyncMock(
                    return_value=InboxDrainStats(
                        fetched=1,
                        absorbed=1,
                        replayed=0,
                    )
                ),
            ) as drain,
            patch(
                f"{command_path}.recover_expired_observations",
                return_value=0,
            ) as recover,
            patch(
                f"{command_path}.claim_observations",
                return_value=(fake_claim,),
            ) as claim,
            patch(
                f"{command_path}.execute_claim",
                return_value=fake_observation,
            ) as execute,
            patch(
                f"{command_path}.observation_backlog",
                return_value=backlog,
            ) as read_backlog,
            patch(
                f"{command_path}.build_direct_http_acquisition",
                return_value=fake_acquisition,
            ) as build_acquisition,
            patch(
                f"{command_path}.build_browser_render_acquisition",
            ) as build_browser_acquisition,
            patch(
                f"{command_path}.Command._heartbeat",
                new_callable=AsyncMock,
            ) as heartbeat,
        ):
            call_command(
                "observer_worker",
                "--queue-name",
                "observer-test",
                "--instance-id",
                "observer-once-test",
                "--enable-http-acquisition",
                "--http-user-agent",
                "MakoloObserver/1.0 Test",
                "--http-host-interval-seconds",
                "0",
                "--once",
                stdout=stdout,
            )

        open_queue.assert_awaited_once()
        drain.assert_awaited_once()
        recover.assert_called_once()
        claim.assert_called_once()
        execute.assert_called_once()
        build_acquisition.assert_called_once()
        build_browser_acquisition.assert_not_called()
        self.assertIs(
            execute.call_args.kwargs["acquisition"],
            fake_acquisition,
        )
        read_backlog.assert_called_once()
        self.assertEqual(heartbeat.await_count, 3)
        final_kwargs = heartbeat.await_args.kwargs
        self.assertEqual(final_kwargs["state"], WorkerState.STOPPED)
        self.assertEqual(
            final_kwargs["metadata"]["last_stats"],
            {
                "inbox_fetched": 1,
                "inbox_absorbed": 1,
                "inbox_replayed": 0,
                "recovered_observations": 0,
                "claimed_observations": 1,
                "observed": 1,
                "not_modified": 0,
                "failed": 0,
                "pending_handoffs": 2,
                "due_retries": 1,
                "due_watches": 0,
                "open_observations": 0,
                "acquisition": "direct_http_v1",
            },
        )

    def test_worker_one_shot_claims_and_executes_browser_work(self):
        queue = FakeDrainQueue()
        stdout = StringIO()
        command_path = (
            "observer.django_app.management.commands.observer_worker"
        )
        backlog = ObservationBacklog(
            pending_handoffs=1,
            due_retries=0,
            due_watches=0,
            open_observations=0,
        )
        fake_claim = object()
        fake_observation = type(
            "FinalizedObservation",
            (),
            {"outcome": ObservationOutcome.OBSERVED.value},
        )()
        fake_acquisition = object()
        with (
            patch(
                f"{command_path}.is_operational_control_enabled",
                return_value=True,
            ),
            patch(
                f"{command_path}.RequestQueue.open",
                new=AsyncMock(return_value=queue),
            ),
            patch(
                f"{command_path}.drain_crawlee_inbox",
                new=AsyncMock(
                    return_value=InboxDrainStats(
                        fetched=1,
                        absorbed=1,
                        replayed=0,
                    )
                ),
            ),
            patch(
                f"{command_path}.recover_expired_observations",
                return_value=0,
            ),
            patch(
                f"{command_path}.claim_observations",
                return_value=(fake_claim,),
            ),
            patch(
                f"{command_path}.execute_claim",
                return_value=fake_observation,
            ) as execute,
            patch(
                f"{command_path}.observation_backlog",
                return_value=backlog,
            ),
            patch(
                f"{command_path}.build_browser_render_acquisition",
                return_value=fake_acquisition,
            ) as build_browser,
            patch(
                f"{command_path}.build_direct_http_acquisition",
            ) as build_http,
            patch(
                f"{command_path}.Command._heartbeat",
                new_callable=AsyncMock,
            ) as heartbeat,
        ):
            call_command(
                "observer_worker",
                "--queue-name",
                "observer-test",
                "--instance-id",
                "observer-browser-once-test",
                "--enable-browser-acquisition",
                "--http-user-agent",
                "MakoloObserver/1.0 BrowserTest",
                "--http-host-interval-seconds",
                "0",
                "--once",
                stdout=stdout,
            )

        build_browser.assert_called_once()
        build_http.assert_not_called()
        execute.assert_called_once()
        self.assertIs(
            execute.call_args.kwargs["acquisition"],
            fake_acquisition,
        )
        final_kwargs = heartbeat.await_args.kwargs
        self.assertEqual(final_kwargs["state"], WorkerState.STOPPED)
        self.assertEqual(
            final_kwargs["metadata"]["mode"],
            "observer-browser-render",
        )
        self.assertEqual(
            final_kwargs["metadata"]["last_stats"]["acquisition"],
            "browser_render_v1",
        )

    def test_worker_rejects_http_and_browser_modes_together(self):
        with self.assertRaisesRegex(
            CommandError,
            "mutuellement exclusifs",
        ):
            call_command(
                "observer_worker",
                "--queue-name",
                "observer-test",
                "--enable-http-acquisition",
                "--enable-browser-acquisition",
                "--http-user-agent",
                "MakoloObserver/1.0 Test",
                "--once",
                stdout=StringIO(),
            )

    def test_worker_requires_user_agent_for_browser_mode(self):
        with self.assertRaisesRegex(
            CommandError,
            "--http-user-agent",
        ):
            call_command(
                "observer_worker",
                "--queue-name",
                "observer-test",
                "--enable-browser-acquisition",
                "--once",
                stdout=StringIO(),
            )

    def test_worker_rechecks_kill_switch_before_claim(self):
        queue = FakeDrainQueue()
        stdout = StringIO()
        command_path = (
            "observer.django_app.management.commands.observer_worker"
        )
        backlog = ObservationBacklog(
            pending_handoffs=1,
            due_retries=0,
            due_watches=0,
            open_observations=0,
        )
        with (
            patch(
                f"{command_path}.is_operational_control_enabled",
                side_effect=[True, False],
            ),
            patch(
                f"{command_path}.RequestQueue.open",
                new=AsyncMock(return_value=queue),
            ),
            patch(
                f"{command_path}.drain_crawlee_inbox",
                new=AsyncMock(
                    return_value=InboxDrainStats(
                        fetched=0,
                        absorbed=0,
                        replayed=0,
                    )
                ),
            ),
            patch(
                f"{command_path}.recover_expired_observations",
                return_value=0,
            ),
            patch(
                f"{command_path}.claim_observations",
            ) as claim,
            patch(
                f"{command_path}.execute_claim",
            ) as execute,
            patch(
                f"{command_path}.observation_backlog",
                return_value=backlog,
            ),
            patch(
                f"{command_path}.build_direct_http_acquisition",
                return_value=object(),
            ),
            patch(
                f"{command_path}.Command._heartbeat",
                new_callable=AsyncMock,
            ),
        ):
            call_command(
                "observer_worker",
                "--queue-name",
                "observer-test",
                "--instance-id",
                "observer-midcycle-stop",
                "--enable-http-acquisition",
                "--http-user-agent",
                "MakoloObserver/1.0 Test",
                "--once",
                stdout=stdout,
            )

        claim.assert_not_called()
        execute.assert_not_called()


@skipUnless(
    connection.vendor == "postgresql",
    "Observer concurrent runtime contracts require PostgreSQL",
)
class ObserverPostgreSQLConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.now = datetime(2026, 9, 20, 4, 0, tzinfo=timezone.utc)
        self.policy = ObserverRuntimePolicy(lease_seconds=60)
        self.target_key = "web_url:v1:" + ("b" * 64)
        self.target = ObservationTarget(
            handoff_key=make_handoff_key(
                target_key=self.target_key,
                handoff_generation=1,
            ),
            target_key=self.target_key,
            handoff_generation=1,
            locator="https://example.test/concurrent",
            kind="web_url",
            requested_at=self.now,
            observation_hints={},
        )
        absorb_observation_target(self.target, absorbed_at=self.now)

    def _run_concurrently(self, callable_factory):
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def run(index):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                results.append(callable_factory(index))
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=run, args=(0,)),
            threading.Thread(target=run, args=(1,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        return results, errors

    def test_concurrent_handoff_absorption_is_idempotent(self):
        target_key = "web_url:v1:" + ("c" * 64)
        target = ObservationTarget(
            handoff_key=make_handoff_key(
                target_key=target_key,
                handoff_generation=1,
            ),
            target_key=target_key,
            handoff_generation=1,
            locator="https://example.test/absorb-race",
            kind="web_url",
            requested_at=self.now,
            observation_hints={},
        )

        results, errors = self._run_concurrently(
            lambda _index: absorb_observation_target(
                target,
                absorbed_at=self.now,
            )
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(
            sum(1 for _handoff, created in results if created),
            1,
        )
        self.assertEqual(
            len({handoff.pk for handoff, _created in results}),
            1,
        )
        self.assertEqual(
            ObserverHandoff.objects.filter(
                handoff_key=target.handoff_key
            ).count(),
            1,
        )

    def test_concurrent_workers_cannot_start_newer_generation_first(self):
        second = ObservationTarget(
            handoff_key=make_handoff_key(
                target_key=self.target_key,
                handoff_generation=2,
            ),
            target_key=self.target_key,
            handoff_generation=2,
            locator=self.target.locator,
            kind=self.target.kind,
            requested_at=self.now + timedelta(seconds=1),
            observation_hints={},
        )
        absorb_observation_target(
            second,
            absorbed_at=self.now + timedelta(seconds=1),
        )

        results, errors = self._run_concurrently(
            lambda index: claim_observations(
                worker_id=f"ordered-worker-{index}",
                policy=self.policy,
                now=self.now + timedelta(seconds=2),
                limit=1,
            )
        )

        self.assertEqual(errors, [])
        self.assertEqual(sum(len(item) for item in results), 1)
        observation = Observation.objects.get(
            series__target_key=self.target_key
        )
        self.assertEqual(
            observation.source_handoff.handoff_generation,
            1,
        )

    def test_concurrent_workers_start_only_one_observation(self):
        results, errors = self._run_concurrently(
            lambda index: claim_observations(
                worker_id=f"worker-{index}",
                policy=self.policy,
                now=self.now + timedelta(seconds=2),
                limit=1,
            )
        )

        self.assertEqual(errors, [])
        self.assertEqual(sum(len(item) for item in results), 1)
        self.assertEqual(
            Observation.objects.filter(
                series__target_key=self.target_key,
                lifecycle="open",
            ).count(),
            1,
        )
        observation = Observation.objects.get(
            series__target_key=self.target_key
        )
        self.assertIsNotNone(observation.claim_token)
        self.assertIn(observation.claimed_by, {"worker-0", "worker-1"})
