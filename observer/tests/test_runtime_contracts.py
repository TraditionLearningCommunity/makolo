from datetime import datetime, timezone
from unittest import TestCase

from observer.contracts import (
    ArtifactOrigin,
    ObservationOutcome,
)
from observer.errors import ObserverContractError
from observer.runtime_contracts import (
    AcquiredArtifact,
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


    def test_runtime_policy_rejects_invalid_watch_interval(self):
        with self.assertRaises(ObserverContractError):
            ObserverRuntimePolicy(watch_interval_seconds=0)

    def test_acquired_artifact_requires_bytes(self):
        with self.assertRaises(ObserverContractError):
            AcquiredArtifact(
                content="not-bytes",
                role="http_response_body",
                captured_at=self.now,
            )

    def test_acquisition_cannot_smuggle_derived_artifact(self):
        with self.assertRaises(ObserverContractError):
            AcquiredArtifact(
                content=b"payload",
                role="derived",
                captured_at=self.now,
                origin=ArtifactOrigin.DERIVED,
            )

    def test_failed_acquisition_cannot_expose_artifacts(self):
        artifact = AcquiredArtifact(
            content=b"payload",
            role="http_response_body",
            captured_at=self.now,
        )
        with self.assertRaises(ObserverContractError):
            AcquisitionResult(
                outcome=ObservationOutcome.FAILED,
                observed_at=self.now,
                failure_code="test.failure",
                artifacts=(artifact,),
            )

    def test_not_modified_cannot_create_artifact(self):
        artifact = AcquiredArtifact(
            content=b"payload",
            role="http_response_body",
            captured_at=self.now,
        )
        with self.assertRaises(ObserverContractError):
            AcquisitionResult(
                outcome=ObservationOutcome.NOT_MODIFIED,
                observed_at=self.now,
                artifacts=(artifact,),
            )
