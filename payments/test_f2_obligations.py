from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from organizations.models import Organization

from .models import (
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentObligationStatus,
)
from .obligation_services import (
    create_payment_obligation,
    mark_obligation_processing,
    satisfy_payment_obligation,
    submit_payment_evidence,
)


User = get_user_model()


class F2CanonicalPaymentObligationTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="f2-profile-payer",
            email="f2-profile-payer@example.test",
            password="x",
        )
        self.space = Organization.objects.create(name="F2 Space payer", created_by=self.profile)

    def subscription_obligation(self, *, payer_profile=None, payer_space=None, key="subscription:test:f2"):
        return create_payment_obligation(
            reason=PaymentObligationReason.SUBSCRIPTION,
            label="F2 fictitious subscription charge",
            amount=Decimal("12.00"),
            currency="usd",
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            payer_profile=payer_profile,
            payer_space=payer_space,
            payee_platform=True,
            source_key=key,
        )

    def test_subscription_profile_and_space_obligations_need_no_journey_and_pay_makolo(self):
        profile_obligation = self.subscription_obligation(payer_profile=self.profile, key="subscription:f2:profile")
        space_obligation = self.subscription_obligation(payer_space=self.space, key="subscription:f2:space")

        for obligation in (profile_obligation, space_obligation):
            self.assertIsNone(obligation.journey_id)
            self.assertIsNone(obligation.commerce_order_id)
            self.assertIsNone(obligation.step_id)
            self.assertEqual(obligation.reason, PaymentObligationReason.SUBSCRIPTION)
            self.assertTrue(obligation.payee_platform)
            self.assertEqual(obligation.currency, "USD")
        self.assertEqual(profile_obligation.payer_profile_id, self.profile.pk)
        self.assertEqual(space_obligation.payer_space_id, self.space.pk)

    def test_payee_xor_and_subscription_payer_are_strict(self):
        with self.assertRaises(ValidationError):
            create_payment_obligation(
                reason=PaymentObligationReason.SUBSCRIPTION,
                label="Invalid payee",
                amount=Decimal("5.00"),
                currency="USD",
                processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
                payer_profile=self.profile,
                payee_platform=True,
                external_payee_name="Not Makolo",
            )
        with self.assertRaises(ValidationError):
            create_payment_obligation(
                reason=PaymentObligationReason.SUBSCRIPTION,
                label="Missing payer",
                amount=Decimal("5.00"),
                currency="USD",
                processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
                payee_platform=True,
            )

    def test_source_key_is_idempotent_without_journey_and_rejects_conflicting_reuse(self):
        first = self.subscription_obligation(payer_profile=self.profile, key="subscription:f2:idempotent")
        second = self.subscription_obligation(payer_profile=self.profile, key="subscription:f2:idempotent")
        self.assertEqual(first.pk, second.pk)
        with self.assertRaises(ValidationError):
            create_payment_obligation(
                reason=PaymentObligationReason.SUBSCRIPTION,
                label="Conflicting replay",
                amount=Decimal("13.00"),
                currency="USD",
                processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
                payer_profile=self.profile,
                payee_platform=True,
                source_key="subscription:f2:idempotent",
            )

    def test_non_journey_lifecycle_and_evidence_contract_are_explicit(self):
        obligation = self.subscription_obligation(payer_profile=self.profile, key="subscription:f2:lifecycle")
        mark_obligation_processing(obligation=obligation)
        obligation.refresh_from_db()
        self.assertEqual(obligation.status, PaymentObligationStatus.PROCESSING)
        satisfy_payment_obligation(obligation=obligation, source="f2-test")
        obligation.refresh_from_db()
        self.assertEqual(obligation.status, PaymentObligationStatus.SATISFIED)
        self.assertIsNotNone(obligation.satisfied_at)

        evidence_obligation = create_payment_obligation(
            reason=PaymentObligationReason.SUBSCRIPTION,
            label="External evidence unsupported for subscription",
            amount=Decimal("9.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            payer_profile=self.profile,
            payee_platform=True,
            source_key="subscription:f2:evidence",
        )
        with self.assertRaisesMessage(ValidationError, "Journey"):
            submit_payment_evidence(
                obligation=evidence_obligation,
                artifact=None,
                actor=self.profile,
                paid_at=timezone.now(),
            )
