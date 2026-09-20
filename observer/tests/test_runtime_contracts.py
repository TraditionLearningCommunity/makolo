from datetime import datetime, timezone
from unittest import TestCase

from observer.contracts import ObservationOutcome
from observer.errors import ObserverContractError
from observer.runtime_contracts import (
    AcquisitionResult,
    ObservationClaim,
    ObserverRuntimePolicy,
)


class ObserverRuntimeContractTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 20, 4, 0, tzinfo=timezone.utc)

    def test_runtime_policy_requires_positive_lease(self):
        with self.assertRaises(ObserverContractError):
            ObserverRuntimePolicy(lease_seconds=0)

    def test_claim_requires_positive_handoff_generation(self):
        with self.assertRaises(ObserverContractError):
            ObservationClaim(
                observation_ref="observer:observation:v1:test",
                claim_token="token",
                worker_id="worker-a",
                leased_until=self.now,
                target_key="target",
                kind="web_url",
                locator="https://example.test/",
                source_handoff_key="handoff",
                source_handoff_generation=0,
            )

    def test_failed_acquisition_requires_failure_code(self):
        with self.assertRaises(ObserverContractError):
            AcquisitionResult(
                outcome=ObservationOutcome.FAILED,
                observed_at=self.now,
            )
