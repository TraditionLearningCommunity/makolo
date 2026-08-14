from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from capacity.models import CapacityReservationStatus
from commerce.models import CommerceOrderStatus
from events.activity_bridge import sync_event_core
from events.models import Event, EventStatus
from organizations.models import Organization
from tickets.models import TicketOrderStatus, TicketType
from tickets.services import create_order

from .models import PaymentMethod, PaymentProvider, PaymentStatus
from .services import complete_payment, fail_payment, initiate_payment


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class PaymentCommerceBridgeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="payment-commerce-bridge",
            email="payment-commerce-bridge@example.com",
            password="Payments-2026!",
        )
        self.space = Organization.objects.create(name="Payment Commerce", created_by=self.user)
        self.event = Event.objects.create(
            organizer=self.user,
            organization=self.space,
            title="Paiement bridge",
            status=EventStatus.PUBLISHED,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
            registration_start_at=timezone.now() - timedelta(days=1),
            registration_end_at=timezone.now() + timedelta(days=1),
        )
        sync_event_core(self.event)
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Payant",
            price=Decimal("20.00"),
            currency="USD",
            quantity_total=2,
            min_per_order=1,
            max_per_order=1,
            is_active=True,
        )

    def make_order(self):
        return create_order(
            buyer=self.user,
            event=self.event,
            customer_name="Participant",
            customer_email=self.user.email,
            selections=[(self.ticket_type, 1)],
        )

    def test_new_payment_references_commerce_order_and_success_commits_capacity(self):
        order = self.make_order()
        reservation = order.items.get().commerce_item.capacity_reservation
        self.assertEqual(reservation.status, CapacityReservationStatus.HELD)
        payment = initiate_payment(
            order=order,
            actor=self.user,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
        )
        payment.refresh_from_db()
        self.assertEqual(payment.commerce_order_id, order.commerce_order_id)
        self.assertEqual(payment.amount, Decimal("20.00"))

        payment = complete_payment(payment=payment, provider_reference="SBX-COMMERCE-001")
        payment.refresh_from_db()
        order.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(order.status, TicketOrderStatus.CONFIRMED)
        self.assertEqual(order.commerce_order.status, CommerceOrderStatus.CONFIRMED)
        self.assertEqual(reservation.status, CapacityReservationStatus.COMMITTED)
        self.assertEqual(order.tickets.count(), 1)
        self.assertIsNotNone(order.tickets.get().access_id)

    def test_failed_payment_keeps_existing_hold_under_event_policy(self):
        order = self.make_order()
        reservation = order.items.get().commerce_item.capacity_reservation
        payment = initiate_payment(
            order=order,
            actor=self.user,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
        )
        fail_payment(payment=payment, failure_code="declined", failure_message="test")
        reservation.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(reservation.status, CapacityReservationStatus.HELD)
        self.assertEqual(order.status, TicketOrderStatus.PENDING)
        self.assertEqual(order.commerce_order.status, CommerceOrderStatus.PENDING)
