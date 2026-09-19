from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase

from prospector.contracts import ProspectingEvidence, ProspectingTarget
from prospector.errors import ProspectorContractError
from prospector.frontier import FrontierClaim
from prospector.observation_contracts import (
    ObservationDisposition,
    ObservationReceipt,
    make_handoff_key,
)
from prospector.policy import GateDecision, GateDisposition, ObservationPolicy
from prospector.runtime import ProspectorRuntime, RuntimePolicy
from prospector.safe_handoff import SafeHandoffResult


class FakeFrontier:
    def __init__(self, claims):
        self.claims = tuple(claims)
        self.completed = []
        self.deferred = []
        self.suppressed = []
        self.claim_calls = []

    async def claim(self, **kwargs):
        self.claim_calls.append(kwargs)
        return self.claims

    async def complete(self, claim):
        self.completed.append(claim)

    async def defer(self, claim, *, available_at):
        self.deferred.append((claim, available_at))

    async def suppress(self, claim, *, reason_code):
        self.suppressed.append((claim, reason_code))


class ScriptedHandoff:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def submit(self, claim, *, policy, requested_at):
        self.calls.append((claim, policy, requested_at))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RuntimeTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        evidence = ProspectingEvidence(
            method="external_index",
            discovered_at=self.now,
            provider="test",
        )
        target = ProspectingTarget(
            target_key="web_url:v1:" + ("a" * 64),
            locator="https://example.test/a",
            kind="web_url",
            first_discovered_at=self.now,
            evidence=(evidence,),
        )
        self.claims = tuple(
            FrontierClaim(
                claim_token=f"claim-{index}",
                worker_id="worker-a",
                leased_until=self.now + timedelta(minutes=5),
                target=target,
                handoff_generation=index,
            )
            for index in (1, 2, 3)
        )
        self.observation_policy = ObservationPolicy(
            policy_key="runtime-test-v1",
            dns_retry_seconds=60,
            pause_retry_seconds=60,
        )
        self.runtime_policy = RuntimePolicy(
            worker_id="worker-a",
            claim_batch_size=3,
            lease_seconds=300,
            exception_retry_seconds=90,
            poll_seconds=1,
        )

    def receipt(self, claim, disposition, *, retry_at=None, reason_code=None):
        return ObservationReceipt(
            handoff_key=make_handoff_key(
                target_key=claim.target.target_key,
                handoff_generation=claim.handoff_generation,
            ),
            target_key=claim.target.target_key,
            handoff_generation=claim.handoff_generation,
            disposition=disposition,
            received_at=self.now,
            observer_ref="observer:test"
            if disposition is not ObservationDisposition.DEFERRED
            else None,
            reason_code=reason_code,
            retry_at=retry_at,
        )

    def allowed(self, receipt):
        return SafeHandoffResult(
            decision=GateDecision(GateDisposition.ALLOW, "admissible"),
            receipt=receipt,
        )

    def runtime(self, frontier, handoff, *, policy=None):
        return ProspectorRuntime(
            frontier=frontier,
            handoff=handoff,
            observation_policy=self.observation_policy,
            runtime_policy=policy or self.runtime_policy,
            clock=lambda: self.now,
        )

    async def test_accepted_and_already_accepted_complete_frontier(self):
        frontier = FakeFrontier(self.claims[:2])
        handoff = ScriptedHandoff(
            [
                self.allowed(
                    self.receipt(
                        self.claims[0],
                        ObservationDisposition.ACCEPTED,
                    )
                ),
                self.allowed(
                    self.receipt(
                        self.claims[1],
                        ObservationDisposition.ALREADY_ACCEPTED,
                    )
                ),
            ]
        )
        stats = await self.runtime(frontier, handoff).run_cycle()
        self.assertEqual(stats.claimed, 2)
        self.assertEqual(stats.completed, 2)
        self.assertEqual(frontier.completed, list(self.claims[:2]))

    async def test_gate_reject_suppresses_and_gate_defer_releases_claim(self):
        retry = self.now + timedelta(minutes=5)
        frontier = FakeFrontier(self.claims[:2])
        handoff = ScriptedHandoff(
            [
                SafeHandoffResult(
                    decision=GateDecision(
                        GateDisposition.REJECT,
                        "security.non_global_address",
                    )
                ),
                SafeHandoffResult(
                    decision=GateDecision(
                        GateDisposition.DEFER,
                        "budget.exhausted",
                        retry_at=retry,
                    )
                ),
            ]
        )
        stats = await self.runtime(frontier, handoff).run_cycle()
        self.assertEqual(stats.suppressed, 1)
        self.assertEqual(stats.deferred, 1)
        self.assertEqual(
            frontier.suppressed[0][1],
            "security.non_global_address",
        )
        self.assertEqual(frontier.deferred[0][1], retry)

    async def test_observer_rejected_suppresses(self):
        frontier = FakeFrontier(self.claims[:1])
        handoff = ScriptedHandoff(
            [
                self.allowed(
                    self.receipt(
                        self.claims[0],
                        ObservationDisposition.REJECTED,
                        reason_code="observer.unsupported_target",
                    )
                )
            ]
        )
        stats = await self.runtime(frontier, handoff).run_cycle()
        self.assertEqual(stats.suppressed, 1)
        self.assertEqual(
            frontier.suppressed[0][1],
            "observer.unsupported_target",
        )

    async def test_observer_deferred_applies_backpressure_to_remaining_claims(self):
        retry = self.now + timedelta(minutes=10)
        frontier = FakeFrontier(self.claims)
        handoff = ScriptedHandoff(
            [
                self.allowed(
                    self.receipt(
                        self.claims[0],
                        ObservationDisposition.DEFERRED,
                        retry_at=retry,
                        reason_code="observer.capacity",
                    )
                )
            ]
        )
        stats = await self.runtime(frontier, handoff).run_cycle()
        self.assertEqual(stats.deferred, 3)
        self.assertEqual(stats.backpressure_released, 2)
        self.assertEqual(len(handoff.calls), 1)
        self.assertEqual(
            [available_at for _claim, available_at in frontier.deferred],
            [retry, retry, retry],
        )

    async def test_backpressure_stop_can_be_disabled_explicitly(self):
        retry = self.now + timedelta(minutes=10)
        policy = RuntimePolicy(
            worker_id="worker-a",
            claim_batch_size=3,
            lease_seconds=300,
            exception_retry_seconds=90,
            poll_seconds=1,
            stop_on_observer_deferred=False,
        )
        frontier = FakeFrontier(self.claims[:2])
        handoff = ScriptedHandoff(
            [
                self.allowed(
                    self.receipt(
                        self.claims[0],
                        ObservationDisposition.DEFERRED,
                        retry_at=retry,
                        reason_code="observer.capacity",
                    )
                ),
                self.allowed(
                    self.receipt(
                        self.claims[1],
                        ObservationDisposition.ACCEPTED,
                    )
                ),
            ]
        )
        stats = await self.runtime(frontier, handoff, policy=policy).run_cycle()
        self.assertEqual(stats.deferred, 1)
        self.assertEqual(stats.completed, 1)
        self.assertEqual(len(handoff.calls), 2)

    async def test_handoff_exception_is_deferred_without_losing_claim(self):
        frontier = FakeFrontier(self.claims[:1])
        handoff = ScriptedHandoff([RuntimeError("observer unavailable")])
        stats = await self.runtime(frontier, handoff).run_cycle()
        self.assertEqual(stats.handoff_errors, 1)
        self.assertEqual(stats.deferred, 1)
        self.assertEqual(
            frontier.deferred[0][1],
            self.now + timedelta(seconds=90),
        )

    async def test_contract_error_is_not_hidden_as_transient_retry(self):
        frontier = FakeFrontier(self.claims[:1])
        handoff = ScriptedHandoff(
            [ProspectorContractError("broken contract")]
        )
        with self.assertRaises(ProspectorContractError):
            await self.runtime(frontier, handoff).run_cycle()
        self.assertEqual(frontier.deferred, [])

    async def test_run_forever_can_be_bounded_for_supervisor_and_tests(self):
        frontier = FakeFrontier(())
        handoff = ScriptedHandoff([])
        runtime = self.runtime(frontier, handoff)
        stop = __import__("asyncio").Event()
        cycles = []

        async def on_cycle(stats):
            cycles.append(stats)

        await runtime.run_forever(
            stop_event=stop,
            on_cycle=on_cycle,
            max_cycles=2,
        )
        self.assertEqual(len(cycles), 2)
        self.assertEqual(len(frontier.claim_calls), 2)
