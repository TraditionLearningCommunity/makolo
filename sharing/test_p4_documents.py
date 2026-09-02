from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity
from journeys.models import Journey, WorkflowKind

from .document_services import (
    absorb_capture_into_journey,
    can_export_journey_artifact,
    create_inbound_capture,
    expire_captures,
)
from .inbound_models import InboundCaptureSourceKind, InboundCaptureStatus


User = get_user_model()


def pdf(name="cv.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n% test\n", content_type="application/pdf")


class P4DocumentTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="p4-owner", password="pass")
        self.other = User.objects.create_user(username="p4-other", password="pass")
        self.activity = Activity.objects.create(title="Bourse P4", created_by=self.owner, owner_profile=self.owner)
        self.journey = Journey.objects.create(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )

    def capture_file(self, name="cv.pdf"):
        return create_inbound_capture(
            actor=self.owner,
            source_kind=InboundCaptureSourceKind.FILE,
            uploaded_file=pdf(name),
        )

    def test_url_capture_rejects_dangerous_schemes_and_private_networks(self):
        for value in ["javascript:alert(1)", "file:///etc/passwd", "data:text/plain,x", "http://127.0.0.1/x"]:
            with self.assertRaises(ValidationError):
                create_inbound_capture(actor=self.owner, source_kind=InboundCaptureSourceKind.URL, source_url=value)
        capture = create_inbound_capture(
            actor=self.owner,
            source_kind=InboundCaptureSourceKind.URL,
            source_url="https://example.org/scholarship#details",
        )
        self.assertEqual(capture.source_url, "https://example.org/scholarship")

    def test_file_capture_validates_extension_and_is_private(self):
        capture = self.capture_file()
        self.assertEqual(capture.created_by, self.owner)
        self.assertEqual(capture.status, InboundCaptureStatus.PENDING)
        self.assertTrue(capture.file.name.startswith(f"sharing/inbound/{self.owner.pk}/"))
        with self.assertRaises(ValidationError):
            create_inbound_capture(
                actor=self.owner,
                source_kind=InboundCaptureSourceKind.FILE,
                uploaded_file=pdf("cv.exe"),
            )

    def test_capture_owner_is_required_for_absorption(self):
        capture = self.capture_file()
        with self.assertRaises(PermissionDenied):
            absorb_capture_into_journey(
                actor=self.other,
                capture_id=capture.pk,
                journey_id=self.journey.pk,
                kind=JourneyArtifactKind.CV,
            )

    def test_file_absorption_is_idempotent_and_creates_recipient_artifact(self):
        capture = self.capture_file()
        first = absorb_capture_into_journey(
            actor=self.owner,
            capture_id=capture.pk,
            journey_id=self.journey.pk,
            kind=JourneyArtifactKind.CV,
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
            title="CV Gilbert",
        )
        second = absorb_capture_into_journey(
            actor=self.owner,
            capture_id=capture.pk,
            journey_id=self.journey.pk,
            kind=JourneyArtifactKind.CV,
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
            title="CV Gilbert",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.journey, self.journey)
        self.assertEqual(first.uploaded_by, self.owner)
        self.assertEqual(self.journey.artifacts.count(), 1)

    def test_identity_document_is_restricted_and_not_exportable(self):
        capture = self.capture_file("passport.pdf")
        artifact = absorb_capture_into_journey(
            actor=self.owner,
            capture_id=capture.pk,
            journey_id=self.journey.pk,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            sensitivity=JourneyArtifactSensitivity.NORMAL,
        )
        self.assertEqual(artifact.sensitivity, JourneyArtifactSensitivity.RESTRICTED)
        self.assertFalse(can_export_journey_artifact(self.owner, artifact).allowed)

    def test_owner_export_allowlist_and_other_profile_denied(self):
        artifact = absorb_capture_into_journey(
            actor=self.owner,
            capture_id=self.capture_file().pk,
            journey_id=self.journey.pk,
            kind=JourneyArtifactKind.CV,
        )
        self.assertTrue(can_export_journey_artifact(self.owner, artifact).allowed)
        self.assertTrue(can_export_journey_artifact(self.owner, artifact).requires_warning)
        self.assertFalse(can_export_journey_artifact(self.other, artifact).allowed)

    def test_payment_receipt_upload_does_not_touch_payment_domain_and_is_not_exportable(self):
        artifact = absorb_capture_into_journey(
            actor=self.owner,
            capture_id=self.capture_file("receipt.pdf").pk,
            journey_id=self.journey.pk,
            kind=JourneyArtifactKind.PAYMENT_RECEIPT,
        )
        self.assertFalse(can_export_journey_artifact(self.owner, artifact).allowed)

    def test_expired_capture_cleanup_does_not_delete_absorbed_artifact(self):
        capture = self.capture_file()
        artifact = absorb_capture_into_journey(
            actor=self.owner,
            capture_id=capture.pk,
            journey_id=self.journey.pk,
            kind=JourneyArtifactKind.CV,
        )
        capture.refresh_from_db()
        capture.expires_at = timezone.now() - timedelta(days=1)
        capture.save(update_fields=["expires_at", "updated_at"])
        self.assertEqual(expire_captures(), 0)
        self.assertTrue(self.journey.artifacts.filter(pk=artifact.pk).exists())

    def test_pending_expired_capture_is_marked_expired(self):
        capture = self.capture_file()
        capture.expires_at = timezone.now() - timedelta(seconds=1)
        capture.save(update_fields=["expires_at", "updated_at"])
        self.assertEqual(expire_captures(), 1)
        capture.refresh_from_db()
        self.assertEqual(capture.status, InboundCaptureStatus.EXPIRED)
