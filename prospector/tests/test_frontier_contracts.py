from datetime import datetime, timezone
from unittest import TestCase

from prospector.contracts import ProspectingEvidence, ProspectingTarget
from prospector.errors import ProspectorContractError
from prospector.frontier import FrontierClaim


class FrontierClaimTests(TestCase):
    def test_claim_requires_an_explicit_target_and_aware_lease(self):
        evidence = ProspectingEvidence(
            method="external_index",
            discovered_at=datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc),
            provider="test-index",
        )
        target = ProspectingTarget(
            target_key="web_url:v1:" + ("a" * 64),
            locator="https://example.test/",
            kind="web_url",
            first_discovered_at=evidence.discovered_at,
            evidence=(evidence,),
        )
        claim = FrontierClaim(
            claim_token="claim-1",
            worker_id="worker-a",
            leased_until=datetime(2026, 9, 18, 9, 5, tzinfo=timezone.utc),
            target=target,
            handoff_generation=1,
        )
        self.assertEqual(claim.worker_id, "worker-a")

        with self.assertRaises(ProspectorContractError):
            FrontierClaim(
                claim_token="claim-2",
                worker_id="worker-b",
                leased_until=datetime(2026, 9, 18, 9, 5),
                target=target,
                handoff_generation=1,
            )
