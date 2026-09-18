from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase

from prospector.contracts import ProspectingEvidence, ProspectingTarget
from prospector.errors import ObservationContractError
from prospector.frontier import FrontierClaim
from prospector.observation_contracts import (
    ObservationDisposition,
    ObservationReceipt,
    make_handoff_key,
)
from prospector.observation_handoff import ObservationHandoff


class IdempotentFakeObserver:
    def __init__(self):
        self.accepted = {}

    async def submit(self, target):
        if target.handoff_key in self.accepted:
            disposition = ObservationDisposition.ALREADY_ACCEPTED
            observer_ref = self.accepted[target.handoff_key]
        else:
            disposition = ObservationDisposition.ACCEPTED
            observer_ref = f"observer:{len(self.accepted) + 1}"
            self.accepted[target.handoff_key] = observer_ref
        return ObservationReceipt(
            handoff_key=target.handoff_key,
            target_key=target.target_key,
            handoff_generation=target.handoff_generation,
            disposition=disposition,
            received_at=target.requested_at,
            observer_ref=observer_ref,
        )


class BadObserver:
    async def submit(self, target):
        other_key = "web_url:v1:" + ("b" * 64)
        return ObservationReceipt(
            handoff_key=make_handoff_key(
                target_key=other_key,
                handoff_generation=target.handoff_generation,
            ),
            target_key=other_key,
            handoff_generation=target.handoff_generation,
            disposition=ObservationDisposition.ACCEPTED,
            received_at=target.requested_at,
            observer_ref="observer:bad",
        )


class ObservationHandoffTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        evidence = ProspectingEvidence(
            method="external_index",
            discovered_at=self.now,
            provider="test-index",
        )
        target = ProspectingTarget(
            target_key="web_url:v1:" + ("a" * 64),
            locator="https://example.test/resource",
            kind="web_url",
            first_discovered_at=self.now,
            evidence=(evidence,),
        )
        self.claim = FrontierClaim(
            claim_token="claim-a",
            worker_id="worker-a",
            leased_until=self.now + timedelta(minutes=5),
            target=target,
            handoff_generation=1,
        )

    async def test_same_generation_is_idempotent_at_observer_boundary(self):
        observer = IdempotentFakeObserver()
        handoff = ObservationHandoff(observer=observer)

        first = await handoff.submit(self.claim, requested_at=self.now)
        second_claim = FrontierClaim(
            claim_token="claim-b",
            worker_id="worker-b",
            leased_until=self.now + timedelta(minutes=10),
            target=self.claim.target,
            handoff_generation=1,
        )
        second = await handoff.submit(
            second_claim,
            requested_at=self.now + timedelta(minutes=6),
        )

        self.assertEqual(first.disposition, ObservationDisposition.ACCEPTED)
        self.assertEqual(
            second.disposition,
            ObservationDisposition.ALREADY_ACCEPTED,
        )
        self.assertEqual(first.observer_ref, second.observer_ref)
        self.assertEqual(len(observer.accepted), 1)

    async def test_new_generation_is_a_new_observation_handoff(self):
        observer = IdempotentFakeObserver()
        handoff = ObservationHandoff(observer=observer)
        await handoff.submit(self.claim, requested_at=self.now)

        new_claim = FrontierClaim(
            claim_token="claim-c",
            worker_id="worker-a",
            leased_until=self.now + timedelta(hours=1),
            target=self.claim.target,
            handoff_generation=2,
        )
        receipt = await handoff.submit(
            new_claim,
            requested_at=self.now + timedelta(hours=1),
        )

        self.assertEqual(receipt.disposition, ObservationDisposition.ACCEPTED)
        self.assertEqual(len(observer.accepted), 2)

    async def test_mismatched_receipt_is_rejected(self):
        handoff = ObservationHandoff(observer=BadObserver())
        with self.assertRaises(ObservationContractError):
            await handoff.submit(self.claim, requested_at=self.now)
