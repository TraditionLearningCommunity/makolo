import hashlib
import uuid
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from prospector.observation_contracts import ObservationTarget, make_handoff_key

from observer.contracts import (
    ArtifactCompleteness,
    ArtifactOrigin,
    ObservationOutcome,
    ObservationTrigger,
)
from observer.django_artifacts import (
    DjangoArtifactReader,
    read_artifact_bytes,
    store_blob,
)
from observer.django_material import (
    DjangoObservationMaterialSource,
    build_observation_material,
)
from observer.django_store import (
    absorb_observation_target,
    get_or_create_observation_series,
)
from observer.errors import ObserverContractError, ObserverStateConflictError
from observer.identifiers import make_reference_key

from .models import (
    Observation,
    ObservationAttempt,
    ObservedArtifact,
    ObservedReference,
    observer_blob_upload_to,
)
from .storage import private_observer_artifact_storage


class ObserverFoundationTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(
            MAKOLO_OBSERVER_ARTIFACT_ROOT=(
                Path(self.temp_dir.name) / "observer-artifacts"
            )
        )
        self.override.enable()
        self.now = datetime(
            2026,
            9,
            19,
            18,
            0,
            tzinfo=timezone.utc,
        )
        self.target_key = "web_url:v1:" + ("a" * 64)
        self.handoff_key = make_handoff_key(
            target_key=self.target_key,
            handoff_generation=1,
        )
        self.target = ObservationTarget(
            handoff_key=self.handoff_key,
            target_key=self.target_key,
            handoff_generation=1,
            locator="https://example.test/resource?x=1",
            kind="web_url",
            requested_at=self.now,
            observation_hints={
                "indexed_mime_type": "text/html"
            },
        )

    def tearDown(self):
        self.override.disable()
        self.temp_dir.cleanup()
        super().tearDown()

    def absorb(self):
        return absorb_observation_target(
            self.target,
            absorbed_at=self.now + timedelta(seconds=1),
        )

    def series(
        self,
        *,
        profile_key="public-http",
        profile_fingerprint="profile-public-http-v1",
    ):
        return get_or_create_observation_series(
            self.target,
            profile_key=profile_key,
            profile_fingerprint=profile_fingerprint,
        )

    def finalized_observation(
        self,
        *,
        outcome=ObservationOutcome.OBSERVED.value,
    ):
        handoff, _created = self.absorb()
        series, _series_created = self.series()
        return Observation.objects.create(
            series=series,
            source_handoff=handoff,
            trigger=ObservationTrigger.HANDOFF.value,
            lifecycle="finalized",
            outcome=outcome,
            started_at=self.now + timedelta(seconds=2),
            observed_at=self.now + timedelta(seconds=3),
            completed_at=self.now + timedelta(seconds=4),
            requested_locator=self.target.locator,
            final_locator=self.target.locator,
            response_status=(
                304
                if outcome
                == ObservationOutcome.NOT_MODIFIED.value
                else 200
            ),
            profile_ref="public-http",
            profile_fingerprint="profile-public-http-v1",
            policy_fingerprint="observer-policy-v1",
        )

    def test_absorb_handoff_is_idempotent_and_does_not_create_observation(self):
        first, created = self.absorb()
        second, created_again = self.absorb()

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            Observation.objects.count(),
            0,
        )

    def test_same_handoff_key_with_different_locator_is_rejected(self):
        self.absorb()
        conflicting = ObservationTarget(
            handoff_key=self.handoff_key,
            target_key=self.target_key,
            handoff_generation=1,
            locator="https://example.test/different",
            kind="web_url",
            requested_at=self.now,
            observation_hints={
                "indexed_mime_type": "text/html"
            },
        )
        with self.assertRaises(ObserverStateConflictError):
            absorb_observation_target(
                conflicting,
                absorbed_at=self.now + timedelta(seconds=1),
            )

    def test_one_handoff_can_back_multiple_observation_profiles(self):
        handoff, _created = self.absorb()
        public_series, public_created = self.series()
        fr_series, fr_created = self.series(
            profile_key="public-http-fr",
            profile_fingerprint="profile-public-http-fr-v1",
        )

        self.assertTrue(public_created)
        self.assertTrue(fr_created)
        self.assertNotEqual(public_series.pk, fr_series.pk)
        self.assertEqual(public_series.target_key, handoff.target_key)
        self.assertEqual(fr_series.target_key, handoff.target_key)

    def test_private_storage_is_outside_media_root_and_has_no_url(self):
        self.assertNotEqual(
            Path(
                private_observer_artifact_storage.location
            ).resolve(),
            Path(settings.MEDIA_ROOT).resolve(),
        )
        with self.assertRaises(ValueError):
            private_observer_artifact_storage.url(
                "sha256/example.bin"
            )

    def test_blob_storage_is_content_addressed_and_deduplicated(self):
        first, created = store_blob(b"same bytes")
        second, created_again = store_blob(b"same bytes")

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertIn(
            first.content_digest,
            first.file.name,
        )
        with first.file.open("rb") as handle:
            self.assertEqual(
                handle.read(),
                b"same bytes",
            )

    def test_blob_storage_recovers_matching_orphan_file(self):
        payload = b"orphaned before database commit"
        digest = hashlib.sha256(payload).hexdigest()
        probe = type("BlobProbe", (), {"content_digest": digest})()
        expected_name = observer_blob_upload_to(
            probe,
            "artifact.bin",
        )
        saved_name = private_observer_artifact_storage.save(
            expected_name,
            ContentFile(payload),
        )
        self.assertEqual(saved_name, expected_name)

        blob, created = store_blob(payload)

        self.assertTrue(created)
        self.assertEqual(blob.file.name, expected_name)
        self.assertEqual(blob.content_digest, digest)

    def test_material_projects_artifact_without_storage_path(self):
        observation = self.finalized_observation()
        attempt = ObservationAttempt.objects.create(
            observation=observation,
            ordinal=1,
            strategy="direct_http",
            lifecycle="finalized",
            outcome="succeeded",
            started_at=self.now + timedelta(seconds=2),
            completed_at=self.now + timedelta(seconds=3),
            requested_locator=self.target.locator,
            final_locator=self.target.locator,
            response_status=200,
            wire_bytes=12,
            decoded_bytes=12,
        )
        blob, _created = store_blob(b"hello world!")
        artifact = ObservedArtifact(
            observation=observation,
            producing_attempt=attempt,
            blob=blob,
            role="response_body",
            origin=ArtifactOrigin.CAPTURED.value,
            completeness=ArtifactCompleteness.COMPLETE.value,
            declared_media_type="text/plain",
            detected_media_type="text/plain",
            charset="utf-8",
            captured_at=self.now + timedelta(seconds=3),
        )
        artifact.full_clean()
        artifact.save()

        material = build_observation_material(
            observation.observation_ref
        )

        self.assertEqual(
            material.outcome,
            ObservationOutcome.OBSERVED,
        )
        self.assertEqual(material.observed_at, observation.observed_at)
        self.assertEqual(material.response_status, 200)
        self.assertEqual(
            material.policy_fingerprint,
            "observer-policy-v1",
        )
        self.assertEqual(len(material.attempts), 1)
        self.assertEqual(
            material.attempts[0].strategy.value,
            "direct_http",
        )
        self.assertEqual(len(material.artifacts), 1)
        descriptor = material.artifacts[0]
        self.assertEqual(
            descriptor.artifact_ref,
            artifact.artifact_ref,
        )
        self.assertEqual(
            descriptor.observation_ref,
            observation.observation_ref,
        )
        self.assertEqual(
            descriptor.content_digest,
            blob.content_digest,
        )
        self.assertFalse(hasattr(descriptor, "file"))
        self.assertFalse(
            hasattr(descriptor, "storage_key")
        )
        self.assertEqual(
            read_artifact_bytes(artifact.artifact_ref),
            b"hello world!",
        )
        self.assertEqual(
            DjangoArtifactReader().read(artifact.artifact_ref),
            b"hello world!",
        )
        self.assertEqual(
            DjangoObservationMaterialSource()
            .get_material(observation.observation_ref)
            .material_key,
            material.material_key,
        )

    def test_not_modified_material_revalidates_previous_artifact(self):
        first = self.finalized_observation()
        blob, _created = store_blob(b"stable")
        artifact = ObservedArtifact.objects.create(
            observation=first,
            blob=blob,
            role="response_body",
            origin=ArtifactOrigin.CAPTURED.value,
            completeness=ArtifactCompleteness.COMPLETE.value,
            captured_at=self.now + timedelta(seconds=3),
        )
        second = Observation.objects.create(
            series=first.series,
            source_handoff=first.source_handoff,
            trigger=ObservationTrigger.WATCH.value,
            lifecycle="finalized",
            outcome=ObservationOutcome.NOT_MODIFIED.value,
            started_at=self.now + timedelta(days=1),
            observed_at=(
                self.now
                + timedelta(days=1, seconds=1)
            ),
            completed_at=(
                self.now
                + timedelta(days=1, seconds=2)
            ),
            requested_locator=self.target.locator,
            final_locator=self.target.locator,
            response_status=304,
            profile_ref="public-http",
            profile_fingerprint="profile-public-http-v1",
            policy_fingerprint="observer-policy-v1",
        )
        second.revalidated_artifacts.add(artifact)

        material = build_observation_material(
            second.observation_ref
        )

        self.assertEqual(material.artifacts, ())
        self.assertEqual(
            material.revalidated_artifact_refs,
            (artifact.artifact_ref,),
        )
        self.assertEqual(len(material.revalidated_artifacts), 1)
        self.assertEqual(
            material.revalidated_artifacts[0].artifact_ref,
            artifact.artifact_ref,
        )
        self.assertEqual(
            material.revalidated_artifacts[0].observation_ref,
            first.observation_ref,
        )
        self.assertTrue(material.has_interpretation_material)

    def test_not_modified_cannot_revalidate_artifact_from_other_profile(self):
        first = self.finalized_observation()
        blob, _created = store_blob(b"stable")
        artifact = ObservedArtifact.objects.create(
            observation=first,
            blob=blob,
            role="response_body",
            origin=ArtifactOrigin.CAPTURED.value,
            completeness=ArtifactCompleteness.COMPLETE.value,
            captured_at=self.now + timedelta(seconds=3),
        )
        other_series, _created = self.series(
            profile_key="public-http-fr",
            profile_fingerprint="profile-public-http-fr-v1",
        )
        second = Observation.objects.create(
            series=other_series,
            source_handoff=first.source_handoff,
            trigger=ObservationTrigger.WATCH.value,
            lifecycle="finalized",
            outcome=ObservationOutcome.NOT_MODIFIED.value,
            started_at=self.now + timedelta(days=1),
            observed_at=self.now + timedelta(days=1, seconds=1),
            completed_at=self.now + timedelta(days=1, seconds=2),
            requested_locator=self.target.locator,
            final_locator=self.target.locator,
            response_status=304,
            profile_ref="public-http-fr",
            profile_fingerprint="profile-public-http-fr-v1",
            policy_fingerprint="observer-policy-v1",
        )
        second.revalidated_artifacts.add(artifact)

        with self.assertRaises(ObserverContractError):
            build_observation_material(second.observation_ref)

    def test_open_observation_requires_real_claim_lease(self):
        handoff, _created = self.absorb()
        series, _series_created = self.series()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Observation.objects.create(
                    series=series,
                    source_handoff=handoff,
                    trigger=ObservationTrigger.HANDOFF.value,
                    lifecycle="open",
                    started_at=self.now + timedelta(seconds=2),
                    requested_locator=self.target.locator,
                    profile_ref="public-http",
                    profile_fingerprint="profile-public-http-v1",
                    policy_fingerprint="observer-policy-v1",
                )

    def test_only_one_open_observation_per_series(self):
        handoff, _created = self.absorb()
        series, _series_created = self.series()
        common = dict(
            series=series,
            source_handoff=handoff,
            trigger=ObservationTrigger.HANDOFF.value,
            lifecycle="open",
            started_at=self.now + timedelta(seconds=2),
            requested_locator=self.target.locator,
            profile_ref="public-http",
            profile_fingerprint="profile-public-http-v1",
            policy_fingerprint="observer-policy-v1",
            claim_token=uuid.uuid4(),
            claimed_by="observer-test",
            lease_expires_at=self.now + timedelta(minutes=5),
        )
        Observation.objects.create(**common)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Observation.objects.create(**common)

    def test_reference_identity_is_explicit_not_global_locator_identity(self):
        observation = self.finalized_observation()
        key = make_reference_key(
            relation="link",
            kind="web_url",
            locator="https://example.test/next",
        )
        row = ObservedReference.objects.create(
            observation=observation,
            reference_key=key,
            relation="link",
            locator="https://example.test/next",
            kind="web_url",
            discovered_at=(
                self.now + timedelta(seconds=3)
            ),
        )
        self.assertEqual(row.reference_key, key)
