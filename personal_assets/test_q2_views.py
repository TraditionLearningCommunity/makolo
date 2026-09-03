from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity
from journeys.collaboration_services import create_artifact
from journeys.models import WorkflowKind
from journeys.services import create_journey

from .models import PersonalAsset
from .services import create_personal_asset, create_personal_asset_version


User = get_user_model()


def pdf_upload(text=b"q2-view"):
    return SimpleUploadedFile("doc.pdf", b"%PDF-1.4\n" + text + b"\n%%EOF", content_type="application/pdf")


class Q2LibraryViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="q2-view-owner", email="q2-view-owner@example.com", password="x")
        self.other = User.objects.create_user(username="q2-view-other", email="q2-view-other@example.com", password="x")
        self.asset = create_personal_asset(controller=self.owner, subject_profile=self.owner, title="Mon CV", kind=JourneyArtifactKind.CV)
        self.version = create_personal_asset_version(actor=self.owner, asset=self.asset, uploaded_file=pdf_upload())
        self.activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="Journey Q2 views")
        self.journey = create_journey(initiated_by=self.owner, beneficiary=self.owner, activity=self.activity, workflow=WorkflowKind.SERVICE)

    def test_list_and_detail_are_controller_scoped(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("personal_assets:list"))
        self.assertContains(response, "Mon CV")
        self.assertEqual(self.client.get(reverse("personal_assets:detail", args=[self.asset.pk])).status_code, 200)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("personal_assets:list")), "Mon CV")
        self.assertEqual(self.client.get(reverse("personal_assets:detail", args=[self.asset.pk])).status_code, 404)

    def test_upload_and_new_version_endpoints_preserve_history(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("personal_assets:add"),
            {"title": "Attestation", "kind": JourneyArtifactKind.CERTIFICATE, "sensitivity": JourneyArtifactSensitivity.NORMAL, "file": pdf_upload(b"initial")},
        )
        self.assertEqual(response.status_code, 302)
        created = PersonalAsset.objects.get(controller=self.owner, title="Attestation")
        v1 = created.versions.get(version=1)
        response = self.client.post(reverse("personal_assets:add-version", args=[created.pk]), {"file": pdf_upload(b"replacement")})
        self.assertEqual(response.status_code, 302)
        v2 = created.versions.get(version=2)
        self.assertEqual(v2.supersedes_id, v1.pk)
        self.assertNotEqual(v2.content_hash, v1.content_hash)
        self.assertTrue(created.versions.filter(pk=v1.pk).exists())

    def test_download_is_private_and_idor_safe(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("personal_assets:download", args=[self.version.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("personal_assets:download", args=[self.version.pk])).status_code, 403)

    def test_use_in_journey_endpoint_creates_snapshot(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("personal_assets:use-in-journey", args=[self.journey.pk]), {"version_id": str(self.version.pk)})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.journey.artifacts.count(), 1)
        self.assertEqual(self.journey.artifacts.get().content_hash, self.version.content_hash)

    def test_save_artifact_endpoint_creates_library_version_with_provenance(self):
        artifact = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload(b"journey-copy"),
            uploaded_by=self.owner,
            kind=JourneyArtifactKind.CERTIFICATE,
            title="Depuis Journey",
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("personal_assets:save-artifact", args=[artifact.pk]),
            {"mode": "new", "title": "Copie Journey", "kind": JourneyArtifactKind.CERTIFICATE},
        )
        self.assertEqual(response.status_code, 302)
        created = PersonalAsset.objects.get(controller=self.owner, title="Copie Journey")
        version = created.versions.get()
        self.assertEqual(version.source_journey_artifact_id, artifact.pk)
        self.assertEqual(version.content_hash, artifact.content_hash)
        self.assertEqual(created.sensitivity, JourneyArtifactSensitivity.SENSITIVE)

    def test_archive_removes_asset_from_main_list_without_deleting_versions(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("personal_assets:archive", args=[self.asset.pk]))
        self.assertEqual(response.status_code, 302)
        self.asset.refresh_from_db()
        self.assertIsNotNone(self.asset.archived_at)
        self.assertTrue(self.asset.versions.filter(pk=self.version.pk).exists())
        self.assertNotContains(self.client.get(reverse("personal_assets:list")), "Mon CV")
