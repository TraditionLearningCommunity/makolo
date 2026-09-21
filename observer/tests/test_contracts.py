from datetime import datetime, timedelta, timezone
from unittest import TestCase

from observer.contracts import (
    ArtifactCompleteness,
    ArtifactDescriptor,
    ArtifactOrigin,
    AttemptLifecycle,
    AttemptOutcome,
    AttemptStrategy,
    Observation,
    ObservationAttempt,
    ObservationLifecycle,
    ObservationMaterial,
    ObservationOutcome,
    ObservationTrigger,
    ObservedArtifact,
    TransformationDescriptor,
    make_material_key,
)
from observer.errors import ObserverContractError


class ObserverContractTests(TestCase):
    def setUp(self):
        self.now = datetime(
            2026,
            9,
            19,
            18,
            0,
            tzinfo=timezone.utc,
        )
        self.digest = "a" * 64

    def test_finalized_failed_observation_requires_failure_code(self):
        with self.assertRaises(ObserverContractError):
            Observation(
                observation_ref="observer:observation:v1:test",
                target_key="web_url:v1:" + ("b" * 64),
                target_kind="web_url",
                source_handoff_key="observation:v1:" + ("c" * 64),
                source_handoff_generation=1,
                trigger=ObservationTrigger.HANDOFF,
                lifecycle=ObservationLifecycle.FINALIZED,
                started_at=self.now,
                observed_at=self.now + timedelta(seconds=1),
                completed_at=self.now + timedelta(seconds=2),
                outcome=ObservationOutcome.FAILED,
                requested_locator="https://example.test/",
                observation_profile_ref="public-http",
                observation_profile_fingerprint="profile-v1",
                policy_fingerprint="policy-v1",
            )

    def test_derived_artifact_requires_provenance(self):
        with self.assertRaises(ObserverContractError):
            ObservedArtifact(
                artifact_ref="observer:artifact:v1:derived",
                observation_ref="observer:observation:v1:test",
                role="native_document_text",
                origin=ArtifactOrigin.DERIVED,
                completeness=ArtifactCompleteness.COMPLETE,
                byte_length=12,
                content_digest=self.digest,
                captured_at=self.now,
            )

    def test_derived_artifact_projects_to_descriptor(self):
        artifact = ObservedArtifact(
            artifact_ref="observer:artifact:v1:derived",
            observation_ref="observer:observation:v1:test",
            role="native_document_text",
            origin=ArtifactOrigin.DERIVED,
            completeness=ArtifactCompleteness.COMPLETE,
            byte_length=12,
            content_digest=self.digest,
            captured_at=self.now,
            source_artifact_ref="observer:artifact:v1:source",
            transformation=TransformationDescriptor(
                name="pdf_text",
                version="1",
            ),
        )
        descriptor = artifact.to_descriptor()
        self.assertEqual(
            descriptor.artifact_ref,
            artifact.artifact_ref,
        )
        self.assertEqual(
            descriptor.transformation.name,
            "pdf_text",
        )

    def test_not_modified_material_revalidates_without_new_artifact(self):
        observation_ref = "observer:observation:v1:304"
        material = ObservationMaterial(
            material_key=make_material_key(
                observation_ref=observation_ref
            ),
            observation_ref=observation_ref,
            target_key="web_url:v1:" + ("b" * 64),
            target_kind="web_url",
            source_handoff_key="observation:v1:" + ("c" * 64),
            source_handoff_generation=1,
            started_at=self.now,
            observed_at=self.now + timedelta(milliseconds=500),
            completed_at=self.now + timedelta(seconds=1),
            requested_locator="https://example.test/",
            observation_profile_ref="public-http",
            observation_profile_fingerprint="profile-v1",
            policy_fingerprint="policy-v1",
            trigger=ObservationTrigger.HANDOFF,
            outcome=ObservationOutcome.NOT_MODIFIED,
            response_status=304,
            revalidated_artifact_refs=(
                "observer:artifact:v1:old",
            ),
        )
        self.assertEqual(material.artifacts, ())

    def test_not_modified_material_cannot_manufacture_new_artifact(self):
        descriptor = ArtifactDescriptor(
            artifact_ref="observer:artifact:v1:new",
            role="response_body",
            origin=ArtifactOrigin.CAPTURED,
            completeness=ArtifactCompleteness.COMPLETE,
            byte_length=4,
            content_digest=self.digest,
            captured_at=self.now,
        )
        observation_ref = "observer:observation:v1:bad-304"
        with self.assertRaises(ObserverContractError):
            ObservationMaterial(
                material_key=make_material_key(
                    observation_ref=observation_ref
                ),
                observation_ref=observation_ref,
                target_key="web_url:v1:" + ("b" * 64),
                target_kind="web_url",
                source_handoff_key="observation:v1:" + ("c" * 64),
                source_handoff_generation=1,
                started_at=self.now,
                observed_at=self.now + timedelta(milliseconds=500),
                completed_at=self.now + timedelta(seconds=1),
                requested_locator="https://example.test/",
                observation_profile_ref="public-http",
                observation_profile_fingerprint="profile-v1",
                policy_fingerprint="policy-v1",
                trigger=ObservationTrigger.HANDOFF,
                outcome=ObservationOutcome.NOT_MODIFIED,
                response_status=304,
                artifacts=(descriptor,),
                revalidated_artifact_refs=(
                    "observer:artifact:v1:old",
                ),
            )


    def test_material_exposes_attempt_provenance_and_availability(self):
        observation_ref = "observer:observation:v1:material"
        attempt = ObservationAttempt(
            attempt_ref="observer:attempt:v1:http",
            observation_ref=observation_ref,
            ordinal=1,
            strategy=AttemptStrategy.DIRECT_HTTP,
            lifecycle=AttemptLifecycle.FINALIZED,
            started_at=self.now,
            completed_at=self.now + timedelta(seconds=1),
            outcome=AttemptOutcome.SUCCEEDED,
            requested_locator="https://example.test/",
            final_locator="https://example.test/",
            response_status=200,
            wire_bytes=12,
            decoded_bytes=12,
        )
        descriptor = ArtifactDescriptor(
            artifact_ref="observer:artifact:v1:body",
            producing_attempt_ref=attempt.attempt_ref,
            role="http_response_body",
            origin=ArtifactOrigin.CAPTURED,
            completeness=ArtifactCompleteness.COMPLETE,
            byte_length=12,
            content_digest=self.digest,
            captured_at=self.now + timedelta(seconds=1),
            declared_media_type="text/html",
            charset="utf-8",
        )
        material = ObservationMaterial(
            material_key=make_material_key(
                observation_ref=observation_ref
            ),
            observation_ref=observation_ref,
            target_key="web_url:v1:" + ("b" * 64),
            target_kind="web_url",
            source_handoff_key="observation:v1:" + ("c" * 64),
            source_handoff_generation=1,
            started_at=self.now,
            observed_at=self.now + timedelta(seconds=1),
            completed_at=self.now + timedelta(seconds=2),
            requested_locator="https://example.test/",
            final_locator="https://example.test/",
            observation_profile_ref="public-http",
            observation_profile_fingerprint="profile-v1",
            policy_fingerprint="policy-v1",
            trigger=ObservationTrigger.HANDOFF,
            outcome=ObservationOutcome.OBSERVED,
            response_status=200,
            attempts=(attempt,),
            artifacts=(descriptor,),
        )

        self.assertTrue(material.has_interpretation_material)
        self.assertEqual(
            material.attempts[0].strategy,
            AttemptStrategy.DIRECT_HTTP,
        )
        self.assertEqual(
            material.artifacts[0].producing_attempt_ref,
            attempt.attempt_ref,
        )

    def test_failed_material_can_distinguish_no_material_from_partial_material(self):
        observation_ref = "observer:observation:v1:failed-empty"
        empty = ObservationMaterial(
            material_key=make_material_key(
                observation_ref=observation_ref
            ),
            observation_ref=observation_ref,
            target_key="web_url:v1:" + ("b" * 64),
            target_kind="web_url",
            source_handoff_key="observation:v1:" + ("c" * 64),
            source_handoff_generation=1,
            started_at=self.now,
            observed_at=self.now + timedelta(seconds=1),
            completed_at=self.now + timedelta(seconds=2),
            requested_locator="https://example.test/",
            observation_profile_ref="public-adaptive",
            observation_profile_fingerprint="profile-v1",
            policy_fingerprint="policy-v1",
            trigger=ObservationTrigger.HANDOFF,
            outcome=ObservationOutcome.FAILED,
            failure_code="browser.navigation_timeout",
        )
        self.assertFalse(empty.has_interpretation_material)
