from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility
from journeys.collaboration_models import JourneyArtifact, JourneyArtifactKind
from payments.models import PaymentEvidence, PaymentObligationProcessingMode, PaymentObligationReason, PaymentStatus
from payments.obligation_services import create_payment_obligation

from .models import ServiceKind
from .services import create_service_details, create_service_journey


User = get_user_model()


def pdf_upload(name="document.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4\nT35 demo document\n%%EOF", content_type="application/pdf")


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class ServiceParticipantActionWebTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser(username="t35-action-manager", email="action-manager@example.test", password="x")
        self.participant = User.objects.create_user(username="t35-action-participant", email="action-participant@example.test", password="x")
        self.other = User.objects.create_user(username="t35-action-other", email="action-other@example.test", password="x")
        activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Aide dossier T35", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC)
        self.service = create_service_details(activity=activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT)
        self.journey = create_service_journey(service=self.service, initiated_by=self.participant, beneficiary=self.participant)

    def test_participant_can_upload_and_version_private_artifact(self):
        self.client.force_login(self.participant)
        upload_url = reverse("services:participant-artifact-upload", kwargs={"pk": self.journey.pk})
        response = self.client.post(upload_url, {"title": "Mon CV", "kind": JourneyArtifactKind.CV, "file": pdf_upload()})
        self.assertEqual(response.status_code, 302)
        artifact = JourneyArtifact.objects.get(journey=self.journey, title="Mon CV", version=1)
        version_url = reverse("services:participant-artifact-version", kwargs={"artifact_pk": artifact.pk})
        response = self.client.post(version_url, {"file": pdf_upload("cv-v2.pdf")})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JourneyArtifact.objects.filter(journey=self.journey, title="Mon CV", version=2, supersedes=artifact).exists())

    def test_artifact_routes_are_idor_safe(self):
        self.client.force_login(self.participant)
        self.client.post(reverse("services:participant-artifact-upload", kwargs={"pk": self.journey.pk}), {"title": "Secret", "kind": JourneyArtifactKind.OTHER, "file": pdf_upload()})
        artifact = JourneyArtifact.objects.get(journey=self.journey, title="Secret")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("services:participant-artifact-upload", kwargs={"pk": self.journey.pk})).status_code, 404)
        self.assertEqual(self.client.get(reverse("services:participant-artifact-version", kwargs={"artifact_pk": artifact.pk})).status_code, 404)

    def test_external_obligation_creates_payment_evidence_without_payment(self):
        obligation = create_payment_obligation(journey=self.journey, reason=PaymentObligationReason.SERVICE_PROCESS, label="Frais tiers", amount=Decimal("20.00"), currency="USD", processing_mode=PaymentObligationProcessingMode.EXTERNAL, external_payee_name="Tiers fictif", created_by=self.manager)
        self.client.force_login(self.participant)
        before_payments = self.journey.payment_obligations.get(pk=obligation.pk).payments.count()
        response = self.client.post(reverse("services:participant-payment-evidence", kwargs={"pk": self.journey.pk, "obligation_pk": obligation.pk}), {"file": pdf_upload("receipt.pdf"), "paid_at": (timezone.now() - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M"), "external_reference": "EXT-DEMO-001"})
        self.assertEqual(response.status_code, 302)
        evidence = PaymentEvidence.objects.get(obligation=obligation)
        self.assertEqual(evidence.submitted_by, self.participant)
        self.assertEqual(evidence.artifact.kind, JourneyArtifactKind.PAYMENT_RECEIPT)
        self.assertEqual(obligation.payments.count(), before_payments)

    def test_payment_evidence_and_provider_obligation_are_idor_safe(self):
        external = create_payment_obligation(journey=self.journey, reason=PaymentObligationReason.SERVICE_PROCESS, label="Frais tiers", amount=Decimal("20.00"), currency="USD", processing_mode=PaymentObligationProcessingMode.EXTERNAL, external_payee_name="Tiers fictif", created_by=self.manager)
        provider = create_payment_obligation(journey=self.journey, reason=PaymentObligationReason.SERVICE_PROCESS, label="Frais Makolo", amount=Decimal("10.00"), currency="USD", processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER, payee_profile=self.manager, created_by=self.manager)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("services:participant-payment-evidence", kwargs={"pk": self.journey.pk, "obligation_pk": external.pk})).status_code, 404)
        self.assertEqual(self.client.get(reverse("payments:obligation-start", kwargs={"obligation_pk": provider.pk})).status_code, 404)

    def test_provider_obligation_uses_existing_sandbox_pipeline(self):
        obligation = create_payment_obligation(journey=self.journey, reason=PaymentObligationReason.SERVICE_PROCESS, label="Frais Makolo", amount=Decimal("10.00"), currency="USD", processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER, payee_profile=self.manager, created_by=self.manager)
        self.client.force_login(self.participant)
        start_url = reverse("payments:obligation-start", kwargs={"obligation_pk": obligation.pk})
        response = self.client.post(start_url, {"provider": "sandbox", "method": "mobile_money", "idempotency_key": "t35-obligation-sandbox"})
        self.assertEqual(response.status_code, 302)
        payment = obligation.payments.get()
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        response = self.client.post(reverse("payments:sandbox-complete", kwargs={"pk": payment.pk}))
        self.assertEqual(response.status_code, 302)
        payment.refresh_from_db()
        obligation.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(obligation.status, "satisfied")
