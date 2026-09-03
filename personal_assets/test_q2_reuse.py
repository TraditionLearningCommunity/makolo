from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity
from journeys.collaboration_services import create_artifact
from journeys.models import WorkflowKind
from journeys.services import create_journey

from .models import PersonalAssetUse
from .services import (
    create_personal_asset,
    create_personal_asset_version,
    save_journey_artifact_to_library,
    use_personal_asset_version_in_journey,
)


User = get_user_model()


def pdf_upload(text):
    return SimpleUploadedFile("cv.pdf", b"%PDF-1.4\n" + text + b"\n%%EOF", content_type="application/pdf")


class Q2ControlledReuseTests(TestCase):
    def setUp(self):
        self.controller = User.objects.create_user(username="q2-controller", email="q2-controller@example.com", password="x")
        self.other = User.objects.create_user(username="q2-other", email="q2-other@example.com", password="x")
        self.manager = User.objects.create_user(username="q2-manager", email="q2-manager@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Q2 Journey")
        grant_activity_role(profile=self.manager, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        self.journey = create_journey(initiated_by=self.controller, beneficiary=self.controller, activity=self.activity, workflow=WorkflowKind.SERVICE)
        self.other_journey = create_journey(initiated_by=self.other, beneficiary=self.other, activity=self.activity, workflow=WorkflowKind.SERVICE)
        self.asset = create_personal_asset(
            controller=self.controller,
            subject_profile=self.controller,
            title="CV durable",
            kind=JourneyArtifactKind.CV,
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
        )
        self.v1 = create_personal_asset_version(actor=self.controller, asset=self.asset, uploaded_file=pdf_upload(b"version-one"))

    def test_library_to_journey_is_exact_snapshot_with_exact_version_provenance(self):
        artifact = use_personal_asset_version_in_journey(actor=self.controller, personal_asset_version=self.v1, journey=self.journey)
        use = PersonalAssetUse.objects.get(journey_artifact=artifact)
        self.assertEqual(use.asset_version_id, self.v1.pk)
        self.assertEqual(use.used_by_id, self.controller.pk)
        self.assertEqual(artifact.content_hash, self.v1.content_hash)
        self.assertEqual(artifact.sensitivity, JourneyArtifactSensitivity.SENSITIVE)
        with artifact.file.open("rb") as stream:
            original_snapshot = stream.read()

        v2 = create_personal_asset_version(actor=self.controller, asset=self.asset, uploaded_file=pdf_upload(b"version-two"))
        artifact.refresh_from_db()
        with artifact.file.open("rb") as stream:
            after_update = stream.read()
        self.assertNotEqual(v2.content_hash, self.v1.content_hash)
        self.assertEqual(artifact.content_hash, self.v1.content_hash)
        self.assertEqual(after_update, original_snapshot)

    def test_library_idor_is_denied_even_when_other_user_has_valid_journey(self):
        with self.assertRaises(PermissionDenied):
            use_personal_asset_version_in_journey(actor=self.other, personal_asset_version=self.v1, journey=self.other_journey)

    def test_journey_write_permission_is_still_required_for_non_beneficiary(self):
        other_asset = create_personal_asset(controller=self.other, subject_profile=self.other, title="Other CV", kind=JourneyArtifactKind.CV)
        other_v1 = create_personal_asset_version(actor=self.other, asset=other_asset, uploaded_file=pdf_upload(b"other"))
        with self.assertRaises(PermissionDenied):
            use_personal_asset_version_in_journey(actor=self.other, personal_asset_version=other_v1, journey=self.journey)

    def test_journey_to_library_preserves_source_and_does_not_mutate_artifact(self):
        artifact = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload(b"journey-source"),
            uploaded_by=self.controller,
            kind=JourneyArtifactKind.CERTIFICATE,
            title="Certificat",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )
        source_hash = artifact.content_hash
        with artifact.file.open("rb") as stream:
            source_bytes = stream.read()
        version = save_journey_artifact_to_library(actor=self.controller, journey_artifact=artifact)
        self.assertEqual(version.source_journey_artifact_id, artifact.pk)
        self.assertEqual(version.asset.sensitivity, JourneyArtifactSensitivity.RESTRICTED)
        self.assertEqual(version.content_hash, source_hash)

        create_personal_asset_version(actor=self.controller, asset=version.asset, uploaded_file=pdf_upload(b"new-library-version"))
        artifact.refresh_from_db()
        with artifact.file.open("rb") as stream:
            after_library_update = stream.read()
        self.assertEqual(artifact.content_hash, source_hash)
        self.assertEqual(after_library_update, source_bytes)

    def test_journey_to_library_denies_user_without_artifact_access_including_restricted(self):
        artifact = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload(b"restricted"),
            uploaded_by=self.controller,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            title="Identité",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            save_journey_artifact_to_library(actor=self.other, journey_artifact=artifact)

    def test_saving_into_existing_asset_never_reduces_sensitivity(self):
        target = create_personal_asset(controller=self.controller, subject_profile=self.controller, title="Dossier", sensitivity=JourneyArtifactSensitivity.NORMAL)
        artifact = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload(b"sensitive"),
            uploaded_by=self.controller,
            kind=JourneyArtifactKind.OTHER,
            title="Pièce sensible",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )
        version = save_journey_artifact_to_library(actor=self.controller, journey_artifact=artifact, asset=target)
        target.refresh_from_db()
        self.assertEqual(target.sensitivity, JourneyArtifactSensitivity.RESTRICTED)
        self.assertEqual(version.source_journey_artifact_id, artifact.pk)
