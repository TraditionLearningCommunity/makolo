from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessCredential, AccessStatus
from activities.models import Activity
from journeys.collaboration_models import (
    JourneyArtifactKind,
    JourneyArtifactSensitivity,
    JourneyStep,
    JourneyStepKind,
)
from journeys.models import Journey, WorkflowKind
from payments.models import Payment

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
        self.owner = User.objects.create_user(
            username="p4-owner",
            email="p4-owner@makolo.test",
            password="pass",
        )
        self.other = User.objects.create_user(
            username="p4-other",
            email="p4-other@makolo.test",
            password="pass",
        )
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

    def absorb_cv(self, **kwargs):
        return absorb_capture_into_journey(
            actor=self.owner,
            capture_id=self.capture_file().pk,
            journey_id=self.journey.pk,
            kind=JourneyArtifactKind.CV,
            title="CV Gilbert",
            **kwargs,
        )

    def test_url_capture_rejects_dangerous_schemes_and_private_networks(self):
        for value in ["javascript:alert(1)", "file:///etc/passwd", "data:text/plain,x", "http://127.0.0.1/x"]:
            with self.assertRaises(ValidationError):
                create_inbound_capture(actor=self.owner, source_kind=InboundCaptureSourceKind.URL, source_url=value)
        capture = create_inbound_capture(
            actor=self.owner,
            source_kind=InboundCaptureSourceKind.URL,
            source_url="https://example.org/scholarship?lang=fr#details",
        )
        self.assertEqual(capture.source_url, "https://example.org/scholarship?lang=fr")

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

    def test_absorption_rejects_step_from_another_journey(self):
        other_journey = Journey.objects.create(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        wrong_step = JourneyStep.objects.create(
            journey=other_journey,
            kind=JourneyStepKind.DOCUMENT,
            title="Mauvaise étape",
        )
        with self.assertRaises(ValidationError):
            absorb_capture_into_journey(
                actor=self.owner,
                capture_id=self.capture_file().pk,
                journey_id=self.journey.pk,
                step_id=wrong_step.pk,
                kind=JourneyArtifactKind.CV,
            )
        self.assertEqual(self.journey.artifacts.count(), 0)

    def test_text_and_url_are_absorbed_as_private_journey_notes_not_truth_objects(self):
        text_capture = create_inbound_capture(
            actor=self.owner,
            source_kind=InboundCaptureSourceKind.TEXT,
            text="Liste de pièces demandées",
        )
        note = absorb_capture_into_journey(
            actor=self.owner,
            capture_id=text_capture.pk,
            journey_id=self.journey.pk,
        )
        self.assertEqual(note.journey, self.journey)
        self.assertEqual(note.author, self.owner)
        self.assertIn("Liste de pièces", note.body)
        url_capture = create_inbound_capture(
            actor=self.owner,
            source_kind=InboundCaptureSourceKind.URL,
            source_url="https://example.org/scholarship",
        )
        url_note = absorb_capture_into_journey(
            actor=self.owner,
            capture_id=url_capture.pk,
            journey_id=self.journey.pk,
        )
        self.assertIn("https://example.org/scholarship", url_note.body)

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
        artifact = self.absorb_cv()
        self.assertTrue(can_export_journey_artifact(self.owner, artifact).allowed)
        self.assertTrue(can_export_journey_artifact(self.owner, artifact).requires_warning)
        self.assertFalse(can_export_journey_artifact(self.other, artifact).allowed)

    def test_download_requires_auth_owner_warning_and_safe_response(self):
        artifact = self.absorb_cv()
        url = reverse("journeys:artifact-download", args=[artifact.pk])
        anonymous = self.client.get(url)
        self.assertEqual(anonymous.status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        warning = self.client.get(url)
        self.assertEqual(warning.status_code, 200)
        self.assertContains(warning, "Makolo ne peut pas retirer une copie")
        response = self.client.get(f"{url}?confirm=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("cv-gilbert-v1.pdf", response["Content-Disposition"].lower())
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_download_missing_file_is_clean_404(self):
        artifact = self.absorb_cv()
        artifact.file.storage.delete(artifact.file.name)
        self.client.force_login(self.owner)
        url = reverse("journeys:artifact-download", args=[artifact.pk])
        self.assertEqual(self.client.get(f"{url}?confirm=1").status_code, 404)

    def test_access_credential_id_cannot_use_generic_document_export_route(self):
        access = Access.objects.create(
            beneficiary=self.owner,
            activity=self.activity,
            journey=self.journey,
            issued_by=self.owner,
            status=AccessStatus.VALID,
        )
        credential = AccessCredential.objects.create(access=access)
        self.client.force_login(self.owner)
        url = reverse("journeys:artifact-download", args=[credential.pk])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_payment_receipt_upload_does_not_touch_payment_domain_and_is_not_exportable(self):
        payment_count = Payment.objects.count()
        artifact = absorb_capture_into_journey(
            actor=self.owner,
            capture_id=self.capture_file("receipt.pdf").pk,
            journey_id=self.journey.pk,
            kind=JourneyArtifactKind.PAYMENT_RECEIPT,
        )
        self.assertEqual(Payment.objects.count(), payment_count)
        self.assertFalse(can_export_journey_artifact(self.owner, artifact).allowed)

    def test_certificate_upload_does_not_gain_verification_state(self):
        artifact = absorb_capture_into_journey(
            actor=self.owner,
            capture_id=self.capture_file("certificate.pdf").pk,
            journey_id=self.journey.pk,
            kind=JourneyArtifactKind.CERTIFICATE,
        )
        self.assertFalse(hasattr(artifact, "verified"))

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
