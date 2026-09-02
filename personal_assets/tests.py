import hashlib
import io
import tempfile
import zipfile

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from journeys.collaboration_models import JourneyArtifactSensitivity
from journeys.models import ExternalBeneficiary
from journeys.storage import private_artifact_storage

from .models import PersonalAsset, PersonalAssetVersion
from .selectors import personal_asset_for_controller, personal_assets_for_controller
from .services import archive_personal_asset, create_personal_asset, create_personal_asset_version, personal_asset_version_for_download


User = get_user_model()


def valid_pdf(name="document.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF", content_type="application/pdf")


def valid_docx():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    return SimpleUploadedFile("document.docx", stream.getvalue(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class PersonalAssetQ1Tests(TestCase):
    def setUp(self):
        self.papa = User.objects.create_user(username="papa", email="papa@example.test", password="x")
        self.junior = User.objects.create_user(username="junior", email="junior@example.test", password="x")
        self.other = User.objects.create_user(username="other", email="other@example.test", password="x")
        self.external = ExternalBeneficiary.objects.create(display_name="Junior externe", created_by=self.papa)

    def tearDown(self):
        for version in PersonalAssetVersion.objects.all():
            if version.file.name:
                version.file.storage.delete(version.file.name)

    def test_profile_subject_controller_can_differ_and_subject_gets_no_access(self):
        asset = create_personal_asset(controller=self.papa, subject_profile=self.junior, title="Passeport", sensitivity=JourneyArtifactSensitivity.RESTRICTED)
        self.assertEqual(asset.controller, self.papa)
        self.assertEqual(asset.subject_profile, self.junior)
        self.assertEqual(asset.sensitivity, JourneyArtifactSensitivity.RESTRICTED)
        self.assertFalse(personal_assets_for_controller(self.junior).exists())
        with self.assertRaises(PersonalAsset.DoesNotExist):
            personal_asset_for_controller(self.junior, asset.pk)

    def test_external_subject_requires_current_creator_provenance(self):
        asset = create_personal_asset(controller=self.papa, subject_external_beneficiary=self.external, title="Acte")
        self.assertEqual(asset.subject_external_beneficiary, self.external)
        with self.assertRaises(PermissionDenied):
            create_personal_asset(controller=self.other, subject_external_beneficiary=self.external, title="Interdit")

    def test_subject_xor_is_enforced(self):
        with self.assertRaises(ValidationError):
            PersonalAsset(controller=self.papa, title="Sans sujet").save()
        with self.assertRaises(ValidationError):
            PersonalAsset(controller=self.papa, title="Deux sujets", subject_profile=self.papa, subject_external_beneficiary=self.external).save()

    def test_versioning_preserves_old_version_hash_and_chain(self):
        asset = create_personal_asset(controller=self.papa, subject_profile=self.papa, title="CV")
        first = create_personal_asset_version(actor=self.papa, asset=asset, uploaded_file=valid_pdf())
        second_upload = SimpleUploadedFile("new.pdf", b"%PDF-1.7\nnew\n%%EOF", content_type="application/pdf")
        second = create_personal_asset_version(actor=self.papa, asset=asset, uploaded_file=second_upload)
        first.refresh_from_db()
        self.assertEqual(first.version, 1)
        self.assertEqual(second.version, 2)
        self.assertEqual(second.supersedes, first)
        self.assertEqual(first.content_hash, hashlib.sha256(b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF").hexdigest())
        self.assertIsNone(first.expires_at)
        with self.assertRaises(ValidationError):
            first.save()

    def test_archive_hides_asset_but_keeps_versions(self):
        asset = create_personal_asset(controller=self.papa, subject_profile=self.papa, title="CV")
        create_personal_asset_version(actor=self.papa, asset=asset, uploaded_file=valid_pdf())
        archive_personal_asset(actor=self.papa, asset=asset)
        self.assertFalse(personal_assets_for_controller(self.papa).filter(pk=asset.pk).exists())
        self.assertEqual(PersonalAssetVersion.objects.filter(asset=asset).count(), 1)

    def test_private_storage_and_idor_download(self):
        asset = create_personal_asset(controller=self.papa, subject_profile=self.papa, title="CV")
        version = create_personal_asset_version(actor=self.papa, asset=asset, uploaded_file=valid_pdf("../../secret.pdf"))
        self.assertIsNone(private_artifact_storage.base_url)
        self.assertTrue(version.file.name.startswith(f"personal_assets/{self.papa.pk}/{asset.pk}/"))
        self.assertNotIn("secret", version.file.name)
        self.assertEqual(personal_asset_version_for_download(actor=self.papa, version_id=version.pk), version)
        with self.assertRaises(PermissionDenied):
            personal_asset_version_for_download(actor=self.other, version_id=version.pk)
        with self.assertRaises(ValueError):
            _ = version.file.url

    def test_docx_reuses_canonical_validator(self):
        asset = create_personal_asset(controller=self.papa, subject_profile=self.papa, title="CV")
        version = create_personal_asset_version(actor=self.papa, asset=asset, uploaded_file=valid_docx())
        self.assertEqual(version.mime_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    def test_invalid_empty_and_false_mime_are_rejected(self):
        asset = create_personal_asset(controller=self.papa, subject_profile=self.papa, title="CV")
        with self.assertRaises(ValidationError):
            create_personal_asset_version(actor=self.papa, asset=asset, uploaded_file=SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf"))
        with self.assertRaises(ValidationError):
            create_personal_asset_version(actor=self.papa, asset=asset, uploaded_file=SimpleUploadedFile("fake.pdf", b"not a pdf", content_type="application/pdf"))
        with self.assertRaises(ValidationError):
            create_personal_asset_version(actor=self.papa, asset=asset, uploaded_file=SimpleUploadedFile("fake.jpg", b"%PDF-1.7", content_type="image/jpeg"))

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=8)
    def test_existing_upload_limit_is_reused(self):
        asset = create_personal_asset(controller=self.papa, subject_profile=self.papa, title="CV")
        with self.assertRaises(ValidationError):
            create_personal_asset_version(actor=self.papa, asset=asset, uploaded_file=SimpleUploadedFile("big.pdf", b"%PDF-123456", content_type="application/pdf"))
