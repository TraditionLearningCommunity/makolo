from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from capacity.models import CapacityPool, CapacityReservationStatus
from journeys.models import JourneyStatus, WorkflowKind
from journeys.services import approve_journey, create_journey, request_approval, submit_journey
from organizations.models import Organization

from .models import CommerceOrderStatus, Offer, OfferStatus, PaymentMode
from .services import cancel_order, confirm_order, create_order, expire_order


class CommerceCoreTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="commerce-user", email="commerce@example.com", password="test-pass-2026")
        self.space = Organization.objects.create(name="Commerce Space", created_by=self.user)
        self.activity = Activity.objects.create(space=self.space, created_by=self.user, title="Concert")
        self.occurrence = Occurrence.objects.create(activity=self.activity, label="Soir", start_at=timezone.now() + timedelta(days=1), end_at=timezone.now() + timedelta(days=1, hours=2))

    def journey(self, workflow=WorkflowKind.PURCHASE, status=JourneyStatus.DRAFT):
        return create_journey(initiated_by=self.user, beneficiary=self.user, activity=self.activity, occurrence=self.occurrence, workflow=workflow, status=status)

    def offer(self, *, price="10.00", currency="USD", payment_mode=PaymentMode.UPFRONT, pool=None, name="Tarif standard"):
        return Offer.objects.create(activity=self.activity, occurrence=self.occurrence, capacity_pool=pool, name=name, unit_price=Decimal(price), currency=currency, payment_mode=payment_mode, status=OfferStatus.ACTIVE)

    def test_free_offer_and_none_order_need_no_payment(self):
        journey = self.journey()
        offer = self.offer(price="0.00", payment_mode=PaymentMode.NONE)
        order = create_order(journey=journey, buyer=self.user, selections=[(offer, 1)], payee_space=self.space)
        self.assertEqual(order.total, Decimal("0.00"))
        self.assertEqual(order.payment_mode, PaymentMode.NONE)
        confirmed = confirm_order(order=order)
        self.assertEqual(confirmed.status, CommerceOrderStatus.CONFIRMED)
        self.assertFalse(hasattr(confirmed, "payments") and confirmed.payments.exists())

    def test_server_price_snapshot_ignores_frontend_unit_price(self):
        journey = self.journey()
        offer = self.offer(price="25.00")
        order = create_order(journey=journey, buyer=self.user, selections=[{"offer": offer, "quantity": 2, "unit_price": "1.00"}], payee_space=self.space)
        item = order.items.get()
        self.assertEqual(item.unit_price, Decimal("25.00"))
        self.assertEqual(item.line_total, Decimal("50.00"))
        offer.unit_price = Decimal("40.00")
        offer.save()
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal("25.00"))
        self.assertEqual(order.total, Decimal("50.00"))

    def test_on_site_order_can_confirm_without_provider_payment(self):
        journey = self.journey()
        offer = self.offer(price="20.00", payment_mode=PaymentMode.ON_SITE)
        order = create_order(journey=journey, buyer=self.user, selections=[(offer, 1)], payee_space=self.space)
        order = confirm_order(order=order)
        self.assertEqual(order.status, CommerceOrderStatus.CONFIRMED)
        self.assertEqual(order.total, Decimal("20.00"))

    def test_upfront_moves_purchase_journey_to_pending_payment(self):
        journey = self.journey()
        offer = self.offer(price="20.00", payment_mode=PaymentMode.UPFRONT)
        create_order(journey=journey, buyer=self.user, selections=[(offer, 1)], payee_space=self.space)
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.PENDING_PAYMENT)

    def test_after_approval_moves_approved_journey_to_pending_payment(self):
        journey = self.journey(workflow=WorkflowKind.ORDER_APPROVAL)
        submit_journey(journey=journey, actor=self.user)
        request_approval(journey=journey, actor=self.user)
        # Permission checks for human decisions are covered by authorization tests;
        # this core test uses the canonical approved state to isolate Commerce.
        from journeys.legacy_bridge import sync_legacy_journey_status
        sync_legacy_journey_status(journey=journey, status=JourneyStatus.APPROVED, actor=None, reason="commerce-test")
        journey.refresh_from_db()
        offer = self.offer(price="30.00", payment_mode=PaymentMode.AFTER_APPROVAL)
        create_order(journey=journey, buyer=self.user, selections=[(offer, 1)], payee_space=self.space)
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.PENDING_PAYMENT)

    def test_capacity_is_held_then_committed(self):
        pool = CapacityPool.objects.create(activity=self.activity, occurrence=self.occurrence, total_quantity=2)
        journey = self.journey()
        offer = self.offer(price="0.00", payment_mode=PaymentMode.NONE, pool=pool)
        order = create_order(journey=journey, buyer=self.user, selections=[(offer, 2)], payee_space=self.space)
        reservation = order.items.get().capacity_reservation
        self.assertEqual(reservation.status, CapacityReservationStatus.HELD)
        confirm_order(order=order)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, CapacityReservationStatus.COMMITTED)

    def test_currency_mismatch_is_rejected(self):
        journey = self.journey()
        usd = self.offer(price="10.00", currency="USD", name="USD")
        cdf = self.offer(price="20000.00", currency="CDF", name="CDF")
        with self.assertRaises(ValidationError):
            create_order(journey=journey, buyer=self.user, selections=[(usd, 1), (cdf, 1)], payee_space=self.space)

    def test_payee_mismatch_is_rejected(self):
        journey = self.journey()
        offer = self.offer(price="10.00")
        other = Organization.objects.create(name="Other Space", created_by=self.user)
        with self.assertRaises(ValidationError):
            create_order(journey=journey, buyer=self.user, selections=[(offer, 1)], payee_space=other)

    def test_cancel_releases_hold_and_expire_is_idempotent(self):
        pool = CapacityPool.objects.create(activity=self.activity, occurrence=self.occurrence, total_quantity=1)
        journey = self.journey()
        offer = self.offer(price="10.00", pool=pool)
        order = create_order(journey=journey, buyer=self.user, selections=[(offer, 1)], payee_space=self.space, expires_at=timezone.now() + timedelta(minutes=5))
        cancel_order(order=order)
        reservation = order.items.get().capacity_reservation
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, CapacityReservationStatus.RELEASED)

        journey2 = self.journey()
        order2 = create_order(journey=journey2, buyer=self.user, selections=[(offer, 1)], payee_space=self.space, expires_at=timezone.now() + timedelta(seconds=1))
        future = timezone.now() + timedelta(minutes=1)
        expired = expire_order(order=order2, now=future)
        self.assertEqual(expired.status, CommerceOrderStatus.EXPIRED)
        self.assertEqual(expire_order(order=expired, now=future).status, CommerceOrderStatus.EXPIRED)
