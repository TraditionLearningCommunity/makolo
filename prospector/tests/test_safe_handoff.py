from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase

from prospector.budget import BudgetReservationDecision
from prospector.contracts import ProspectingEvidence, ProspectingTarget
from prospector.frontier import FrontierClaim
from prospector.observation_contracts import (
    ObservationDisposition,
    ObservationReceipt,
)
from prospector.policy import GateDisposition, ObservationPolicy
from prospector.safe_handoff import SafeObservationHandoff
from prospector.security import ObservationGate


class FakeDns:
    async def resolve(self, hostname):
        return ("93.184.216.34",)


class FakeDomain:
    def registrable_domain(self, hostname):
        return hostname


class FakeBudget:
    async def reserve(self, **kwargs):
        return BudgetReservationDecision(
            allowed=True,
            retry_at=None,
            scopes=kwargs["scopes"],
        )


class CountingObserver:
    def __init__(self):
        self.calls = 0

    async def submit(self, target):
        self.calls += 1
        return ObservationReceipt(
            handoff_key=target.handoff_key,
            target_key=target.target_key,
            handoff_generation=target.handoff_generation,
            disposition=ObservationDisposition.ACCEPTED,
            received_at=target.requested_at,
            observer_ref="obs:1",
        )


class SafeObservationHandoffTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        evidence = ProspectingEvidence(
            method="external_index",
            discovered_at=self.now,
            provider="test",
        )
        target = ProspectingTarget(
            target_key="web_url:v1:" + ("a" * 64),
            locator="https://example.test/path",
            kind="web_url",
            first_discovered_at=self.now,
            evidence=(evidence,),
        )
        self.claim = FrontierClaim(
            claim_token="claim",
            worker_id="worker",
            leased_until=self.now + timedelta(minutes=5),
            target=target,
            handoff_generation=1,
        )

    def policy(self, **kwargs):
        return ObservationPolicy(
            policy_key="safe-v1",
            dns_retry_seconds=60,
            pause_retry_seconds=60,
            **kwargs,
        )

    def safe(self, observer):
        return SafeObservationHandoff(
            gate=ObservationGate(
                dns_resolver=FakeDns(),
                domain_scope=FakeDomain(),
                budget_store=FakeBudget(),
            ),
            observer=observer,
        )

    async def test_kill_switch_never_calls_observer(self):
        observer = CountingObserver()
        result = await self.safe(observer).submit(
            self.claim,
            policy=self.policy(enabled=False),
            requested_at=self.now,
        )
        self.assertEqual(result.decision.disposition, GateDisposition.DEFER)
        self.assertIsNone(result.receipt)
        self.assertEqual(observer.calls, 0)

    async def test_allowed_target_calls_observer_once(self):
        observer = CountingObserver()
        result = await self.safe(observer).submit(
            self.claim,
            policy=self.policy(),
            requested_at=self.now,
        )
        self.assertEqual(result.decision.disposition, GateDisposition.ALLOW)
        self.assertEqual(result.receipt.disposition, ObservationDisposition.ACCEPTED)
        self.assertEqual(observer.calls, 1)
