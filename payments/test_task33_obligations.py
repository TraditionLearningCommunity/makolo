from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyArtifactKind, JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey, create_artifact
from payments.models import (
    Payment,
    PaymentEvidenceStatus,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentObligationStatus,
    PaymentProvider,
    PaymentStatus,
)
from services.models import ServiceKind
from services.services import create_service_details, create_service_journey

from .obligation_services import create_payment_obligation, reject_payment_evidence, submit_payment_evidence, verify_payment_evidence
from .services import cancel_payment, complete_sandbox_payment, fail_payment, initiate_obligation_payment
from .tests import make_paid_order


User = get_user_model()


def receipt_upload(text=b"receipt"):
    return SimpleUploadedFile("receipt.pdf", b"%PDF-1.4\n" + text + b"\n%%EOF", content_type="application/pdf")


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class PaymentObligationTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="t33-pay-manager", email="t33-pay-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t33-pay-beneficiary", email="t33-pay-beneficiary@example.com", password="x")
        self.outsider = User.objects.create_user(username="t33-pay-outsider", email="t33-pay-outsider@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="T33 Service payments")
        grant_activity_role(profile=self.manager, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        self.service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.APPLICATION_SUPPORT)
        self.journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary)
        assign_journey(journey=self.journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)

    def obligation(self, *, mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER, key="t33:service:fee"):
        return create_payment_obligation(
            journey=self.journey,
            reason=PaymentObligationReason.SERVICE_PROCESS,
            label="Frais externe",
            amount=Decimal("50.00"),
            currency="usd",
            processing_mode=mode,
            external_payee_name="Université X",
            created_by=self.manager,
            source_key=key,
        )

    def test_multiple_attempts_failed_cancelled_then_success_satisfy_one_obligation(self):
        obligation = self.obligation()
        first = initiate_obligation_payment(obligation=obligation, actor=self.beneficiary, provider=PaymentProvider.SANDBOX, method="mobile_money", idempotency_key="t33-attempt-1")
        fail_payment(payment=first, failure_code="declined")
        obligation.refresh_from_db()
        self.assertEqual(obligation.status, PaymentObligationStatus.PENDING)

        second = initiate_obligation_payment(obligation=obligation, actor=self.beneficiary, provider=PaymentProvider.SANDBOX, method="mobile_money", idempotency_key="t33-attempt-2")
        cancel_payment(payment=second, actor=self.beneficiary)
        obligation.refresh_from_db()
        self.assertEqual(obligation.status, PaymentObligationStatus.PENDING)

        third = initiate_obligation_payment(obligation=obligation, actor=self.beneficiary, provider=PaymentProvider.SANDBOX, method="mobile_money", idempotency_key="t33-attempt-3")
        complete_sandbox_payment(payment=third, actor=self.beneficiary)
        obligation.refresh_from_db()
        third.refresh_from_db()
        self.assertEqual(third.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(obligation.status, PaymentObligationStatus.SATISFIED)
        self.assertIsNotNone(obligation.satisfied_at)
        self.assertEqual(Payment.objects.filter(obligation=obligation).count(), 3)
        with self.assertRaises(ValidationError):
            initiate_obligation_payment(obligation=obligation, actor=self.beneficiary, provider=PaymentProvider.SANDBOX, method="card")

    def test_external_evidence_satisfies_without_fake_payment_and_rejection_keeps_history(self):
        obligation = self.obligation(mode=PaymentObligationProcessingMode.EXTERNAL, key="t33:external:fee")
        artifact1 = create_artifact(journey=self.journey, uploaded_file=receipt_upload(b"bad"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.PAYMENT_RECEIPT, title="Reçu v1")
        evidence1 = submit_payment_evidence(obligation=obligation, artifact=artifact1, actor=self.beneficiary, paid_at=timezone.now())
        reject_payment_evidence(evidence=evidence1, actor=self.manager, review_note="Référence illisible")
        evidence1.refresh_from_db()
        self.assertEqual(evidence1.status, PaymentEvidenceStatus.REJECTED)
        self.assertTrue(type(artifact1).objects.filter(pk=artifact1.pk).exists())

        artifact2 = create_artifact(journey=self.journey, uploaded_file=receipt_upload(b"good"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.PAYMENT_RECEIPT, title="Reçu v2")
        evidence2 = submit_payment_evidence(obligation=obligation, artifact=artifact2, actor=self.beneficiary, paid_at=timezone.now(), external_reference="UNI-50")
        before = Payment.objects.count()
        verify_payment_evidence(evidence=evidence2, actor=self.manager, review_note="Vérifié")
        obligation.refresh_from_db()
        self.assertEqual(obligation.status, PaymentObligationStatus.SATISFIED)
        self.assertEqual(Payment.objects.count(), before)

    def test_cross_journey_artifact_and_outsider_actions_are_denied(self):
        obligation = self.obligation(mode=PaymentObligationProcessingMode.EXTERNAL, key="t33:external:idor")
        other_journey = create_service_journey(service=self.service, initiated_by=self.outsider, beneficiary=self.outsider)
        foreign_artifact = create_artifact(journey=other_journey, uploaded_file=receipt_upload(), uploaded_by=self.outsider, kind=JourneyArtifactKind.PAYMENT_RECEIPT, title="Foreign")
        with self.assertRaises(ValidationError):
            submit_payment_evidence(obligation=obligation, artifact=foreign_artifact, actor=self.beneficiary, paid_at=timezone.now())
        own_artifact = create_artifact(journey=self.journey, uploaded_file=receipt_upload(), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.PAYMENT_RECEIPT, title="Own")
        evidence = submit_payment_evidence(obligation=obligation, artifact=own_artifact, actor=self.beneficiary, paid_at=timezone.now())
        with self.assertRaises(PermissionDenied):
            verify_payment_evidence(evidence=evidence, actor=self.outsider)
        with self.assertRaises(PermissionDenied):
            initiate_obligation_payment(obligation=self.obligation(key="t33:idor:provider"), actor=self.outsider, provider=PaymentProvider.SANDBOX, method="card")

    def test_currency_is_normalized_and_payee_is_explicit(self):
        obligation = self.obligation()
        self.assertEqual(obligation.currency, "USD")
        self.assertEqual(obligation.external_payee_name, "Université X")
        with self.assertRaises(ValidationError):
            create_payment_obligation(
                journey=self.journey,
                reason=PaymentObligationReason.OTHER,
                label="Invalid",
                amount=Decimal("10.00"),
                currency="US",
                processing_mode=PaymentObligationProcessingMode.EXTERNAL,
                external_payee_name="Tiers",
                created_by=self.manager,
            )


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class PaymentObligationLegacyCompatibilityTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(username="t33-event-organizer", email="t33-event-organizer@example.com", password="x", is_organizer=True)
        self.buyer = User.objects.create_user(username="t33-event-buyer", email="t33-event-buyer@example.com", password="x")
        self.event, self.ticket_type, self.order = make_paid_order(self.organizer, self.buyer)

    def test_event_payment_keeps_legacy_sources_and_adds_canonical_obligation(self):
        from .services import initiate_payment
        payment = initiate_payment(order=self.order, actor=self.buyer, provider=PaymentProvider.SANDBOX, method="mobile_money", idempotency_key="t33-event-payment")
        self.assertEqual(payment.order_id, self.order.pk)
        self.assertEqual(payment.commerce_order_id, self.order.commerce_order_id)
        self.assertIsNotNone(payment.obligation_id)
        self.assertEqual(payment.obligation.commerce_order_id, self.order.commerce_order_id)
        self.assertEqual(payment.obligation.journey_id, self.order.journey_id)
        complete_sandbox_payment(payment=payment, actor=self.buyer)
        payment.obligation.refresh_from_db()
        self.assertEqual(payment.obligation.status, PaymentObligationStatus.SATISFIED)
