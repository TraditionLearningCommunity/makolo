from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from capacity.models import CapacityPool, CapacityReservation
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization
from payments.models import Payment

from .models import Offer, OfferStatus, PaymentMode
from .services import confirm_order, create_order


class CommerceOrderInvariantTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="commerce-order-invariants",
            email="commerce-order-invariants@example.com",
            password="Commerce-2026!",
        )
        self.space = Organization.objects.create(name="Commerce Invariants", created_by=self.user)
        self.activity = Activity.objects.create(space=self.space, created_by=self.user, title="Commerce invariants")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=2),
        )

    def journey(self):
        return create_journey(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.PURCHASE,
        )

    def offer(self, name, price, mode, pool=None):
        return Offer.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            capacity_pool=pool,
            name=name,
            unit_price=Decimal(price),
            currency="USD",
            payment_mode=mode,
            status=OfferStatus.ACTIVE,
        )

    def test_multiline_order_keeps_server_snapshots(self):
        journey = self.journey()
        first = self.offer("Tarif A", "10.00", PaymentMode.UPFRONT)
        second = self.offer("Tarif B", "7.50", PaymentMode.UPFRONT)
        order = create_order(
            journey=journey,
            buyer=self.user,
            payee_space=self.space,
            selections=[(first, 2), (second, 1)],
        )
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.subtotal, Decimal("27.50"))
        self.assertEqual(order.total, Decimal("27.50"))
        self.assertEqual(
            list(order.items.order_by("unit_price").values_list("unit_price", flat=True)),
            [Decimal("7.50"), Decimal("10.00")],
        )

    def test_upfront_cannot_confirm_without_successful_payment(self):
        journey = self.journey()
        offer = self.offer("Upfront", "20.00", PaymentMode.UPFRONT)
        order = create_order(
            journey=journey,
            buyer=self.user,
            payee_space=self.space,
            selections=[(offer, 1)],
        )
        with self.assertRaises(ValidationError):
            confirm_order(order=order)

    def test_later_can_confirm_positive_amount_without_provider_payment(self):
        journey = self.journey()
        offer = self.offer("À payer plus tard", "20.00", PaymentMode.LATER)
        order = create_order(
            journey=journey,
            buyer=self.user,
            payee_space=self.space,
            selections=[(offer, 1)],
        )
        confirmed = confirm_order(order=order)
        self.assertEqual(confirmed.total, Decimal("20.00"))
        self.assertEqual(confirmed.payment_mode, PaymentMode.LATER)
        self.assertEqual(Payment.objects.filter(commerce_order=confirmed).count(), 0)

    def test_idempotency_key_does_not_double_reserve_capacity(self):
        pool = CapacityPool.objects.create(activity=self.activity, occurrence=self.occurrence, total_quantity=2)
        journey = self.journey()
        offer = self.offer("Limité", "5.00", PaymentMode.UPFRONT, pool=pool)
        first = create_order(
            journey=journey,
            buyer=self.user,
            payee_space=self.space,
            selections=[(offer, 1)],
            idempotency_key="checkout-double-click-001",
        )
        second = create_order(
            journey=journey,
            buyer=self.user,
            payee_space=self.space,
            selections=[(offer, 1)],
            idempotency_key="checkout-double-click-001",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(CapacityReservation.objects.filter(journey=journey).count(), 1)
