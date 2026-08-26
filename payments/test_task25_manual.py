from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from activities.services import create_activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from commerce.models import OfferStatus, PaymentMode
from commerce.services import OrderSelection, confirm_order, create_offer, create_order
from journeys.models import WorkflowKind
from journeys.services import create_journey, submit_journey

from .manual_services import record_manual_commerce_payment
from .models import Payment, PaymentMethod, PaymentProvider, PaymentStatus


class Task25ManualPaymentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="personal-owner-t25", email="owner-t25@example.test", password="pass-12345")
        self.finance = User.objects.create_user(username="personal-finance-t25", email="finance-t25@example.test", password="pass-12345")
        self.activity = create_activity(owner_profile=self.owner, created_by=self.owner, title="Atelier personnel T25")
        self.offer = create_offer(
            activity=self.activity,
            name="Réservation sur place",
            unit_price=Decimal("20.00"),
            currency="USD",
            payment_mode=PaymentMode.ON_SITE,
            status=OfferStatus.ACTIVE,
        )
        self.journey = create_journey(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            workflow=WorkflowKind.RESERVATION,
        )
        self.journey = submit_journey(journey=self.journey, actor=self.owner, reason="t25-personal-onsite")
        self.order = create_order(
            journey=self.journey,
            buyer=self.owner,
            payee_profile=self.owner,
            selections=[OrderSelection(offer=self.offer, quantity=1, beneficiary=self.owner)],
            payment_mode=PaymentMode.ON_SITE,
            idempotency_key="t25-personal-onsite-order",
        )
        self.order = confirm_order(order=self.order, actor=self.owner)

    def test_personal_activity_order_has_profile_payee_without_fake_space(self):
        self.assertIsNone(self.activity.space_id)
        self.assertEqual(self.activity.owner_profile_id, self.owner.pk)
        self.assertIsNone(self.order.payee_space_id)
        self.assertEqual(self.order.payee_profile_id, self.owner.pk)
        self.assertEqual(self.order.payment_mode, PaymentMode.ON_SITE)
        self.assertEqual(Payment.objects.filter(commerce_order=self.order).count(), 0)

    def test_activity_manager_is_not_implicitly_finance(self):
        with self.assertRaises(PermissionDenied):
            record_manual_commerce_payment(
                commerce_order=self.order,
                actor=self.owner,
                idempotency_key="t25-manual-owner-without-finance",
            )
        self.assertFalse(Payment.objects.filter(commerce_order=self.order).exists())

    def test_activity_finance_mandate_can_record_real_cash_once(self):
        grant_activity_role(
            profile=self.finance,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_FINANCE,
            granted_by=self.owner,
            source="t25-test",
        )
        first = record_manual_commerce_payment(
            commerce_order=self.order,
            actor=self.finance,
            method=PaymentMethod.CASH,
            provider_reference="CASH-T25-001",
            idempotency_key="t25-cash-payment",
        )
        second = record_manual_commerce_payment(
            commerce_order=self.order,
            actor=self.finance,
            method=PaymentMethod.CASH,
            provider_reference="CASH-T25-001",
            idempotency_key="t25-cash-payment",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.provider, PaymentProvider.MANUAL)
        self.assertEqual(first.method, PaymentMethod.CASH)
        self.assertEqual(first.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(first.amount, Decimal("20.00"))
        self.assertEqual(Payment.objects.filter(commerce_order=self.order, status=PaymentStatus.SUCCEEDED).count(), 1)
