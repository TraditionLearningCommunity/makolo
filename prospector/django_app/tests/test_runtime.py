from datetime import datetime, timedelta, timezone

from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_app.models import ProspectorFrontierEntry
from prospector.django_frontier import DjangoFrontierStore
from prospector.frontier import FrontierState
from prospector.observation_contracts import (
    ObservationDisposition,
    ObservationReceipt,
    make_handoff_key,
)
from prospector.policy import GateDecision, GateDisposition, ObservationPolicy
from prospector.runtime import ProspectorRuntime, RuntimePolicy
from prospector.safe_handoff import SafeHandoffResult


class AcceptingHandoff:
    async def submit(self, claim, *, policy, requested_at):
        return SafeHandoffResult(
            decision=GateDecision(GateDisposition.ALLOW, "admissible"),
            receipt=ObservationReceipt(
                handoff_key=make_handoff_key(
                    target_key=claim.target.target_key,
                    handoff_generation=claim.handoff_generation,
                ),
                target_key=claim.target.target_key,
                handoff_generation=claim.handoff_generation,
                disposition=ObservationDisposition.ACCEPTED,
                received_at=requested_at,
                observer_ref="observer:test",
            ),
        )


class DeferringHandoff:
    def __init__(self, retry_at):
        self.retry_at = retry_at

    async def submit(self, claim, *, policy, requested_at):
        return SafeHandoffResult(
            decision=GateDecision(GateDisposition.ALLOW, "admissible"),
            receipt=ObservationReceipt(
                handoff_key=make_handoff_key(
                    target_key=claim.target.target_key,
                    handoff_generation=claim.handoff_generation,
                ),
                target_key=claim.target.target_key,
                handoff_generation=claim.handoff_generation,
                disposition=ObservationDisposition.DEFERRED,
                received_at=requested_at,
                reason_code="observer.capacity",
                retry_at=self.retry_at,
            ),
        )


class DjangoProspectorRuntimeTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        self.frontier = DjangoFrontierStore()
        self.observation_policy = ObservationPolicy(
            policy_key="runtime-db-test-v1",
            dns_retry_seconds=60,
            pause_retry_seconds=60,
        )
        self.runtime_policy = RuntimePolicy(
            worker_id="runtime-db-worker",
            claim_batch_size=2,
            lease_seconds=60,
            exception_retry_seconds=30,
            poll_seconds=1,
        )

    def admit(self, suffix):
        return self.frontier.admit_sync(
            ProspectingCandidate(
                locator=f"https://example.test/{suffix}",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        discovered_at=self.now,
                        provider="test",
                    ),
                ),
            )
        )

    def runtime(self, handoff):
        return ProspectorRuntime(
            frontier=self.frontier,
            handoff=handoff,
            observation_policy=self.observation_policy,
            runtime_policy=self.runtime_policy,
            clock=lambda: self.now,
        )

    def test_accepted_handoff_completes_durable_frontier_entry(self):
        target = self.admit("accepted")
        stats = async_to_sync(self.runtime(AcceptingHandoff()).run_cycle)()

        self.assertEqual(stats.completed, 1)
        entry = ProspectorFrontierEntry.objects.get(target_key=target.target_key)
        self.assertEqual(entry.status, FrontierState.COMPLETED.value)
        self.assertIsNotNone(entry.completed_at)
        self.assertIsNone(entry.lease_expires_at)

    def test_observer_backpressure_releases_claims_to_same_retry_time(self):
        first = self.admit("a")
        second = self.admit("b")
        retry_at = self.now + timedelta(minutes=5)

        stats = async_to_sync(
            self.runtime(DeferringHandoff(retry_at)).run_cycle
        )()

        self.assertEqual(stats.claimed, 2)
        self.assertEqual(stats.deferred, 2)
        self.assertEqual(stats.backpressure_released, 1)
        for target in (first, second):
            entry = ProspectorFrontierEntry.objects.get(target_key=target.target_key)
            self.assertEqual(entry.status, FrontierState.READY.value)
            self.assertEqual(entry.available_at, retry_at)
            self.assertIsNone(entry.lease_expires_at)
