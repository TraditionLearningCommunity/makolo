from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from capacity.models import CapacityReservationStatus
from commerce.models import CommerceOrderStatus, PaymentMode
from events.activity_bridge import sync_event_core
from events.models import Event, EventStatus
from organizations.models import Organization

from .models import TicketOrderStatus, TicketType
from .services import create_order


class EventCommerceCapacityBridgeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="event-commerce-bridge",
            email="event-commerce-bridge@example.com",
            password="Commerce-2026!",
        )
        self.space = Organization.objects.create(name="Event Commerce", created_by=self.user)
        self.event = Event.objects.create(
            organizer=self.user,
            organization=self.space,
            title="Concert bridge",
            status=EventStatus.PUBLISHED,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
            registration_start_at=timezone.now() - timedelta(days=1),
            registration_end_at=timezone.now() + timedelta(days=1),
        )
        sync_event_core(self.event)

    def ticket_type(self, *, name="Standard", price="25.00", quantity=4):
        return TicketType.objects.create(
            event=self.event,
            name=name,
            price=Decimal(price),
            currency="USD",
            quantity_total=quantity,
            min_per_order=1,
            max_per_order=3,
            is_active=True,
        )

    def test_ticket_type_creates_and_updates_offer_and_capacity(self):
        ticket_type = self.ticket_type()
        ticket_type.refresh_from_db()
        self.assertIsNotNone(ticket_type.offer_id)
        self.assertIsNotNone(ticket_type.capacity_pool_id)
        self.assertEqual(ticket_type.offer.unit_price, Decimal("25.00"))
        self.assertEqual(ticket_type.offer.payment_mode, PaymentMode.UPFRONT)
        self.assertEqual(ticket_type.capacity_pool.total_quantity, 4)

        ticket_type.price = Decimal("30.00")
        ticket_type.quantity_total = 6
        ticket_type.name = "Premium"
        ticket_type.save()
        ticket_type.offer.refresh_from_db()
        ticket_type.capacity_pool.refresh_from_db()
        self.assertEqual(ticket_type.offer.unit_price, Decimal("30.00"))
        self.assertEqual(ticket_type.offer.name, "Premium")
        self.assertEqual(ticket_type.capacity_pool.total_quantity, 6)

    def test_paid_event_order_creates_canonical_order_item_and_hold(self):
        ticket_type = self.ticket_type()
        order = create_order(
            buyer=self.user,
            event=self.event,
            customer_name="Participant",
            customer_email=self.user.email,
            selections=[(ticket_type, 2)],
        )
        order.refresh_from_db()
        self.assertIsNotNone(order.journey_id)
        self.assertIsNotNone(order.commerce_order_id)
        self.assertEqual(order.commerce_order.payee_space, self.space)
        self.assertEqual(order.commerce_order.total, Decimal("50.00"))
        self.assertEqual(order.commerce_order.payment_mode, PaymentMode.UPFRONT)

        legacy_item = order.items.get()
        self.assertIsNotNone(legacy_item.commerce_item_id)
        canonical_item = legacy_item.commerce_item
        self.assertEqual(canonical_item.unit_price, Decimal("25.00"))
        self.assertEqual(canonical_item.quantity, 2)
        self.assertEqual(canonical_item.capacity_reservation.quantity, 2)
        self.assertEqual(canonical_item.capacity_reservation.status, CapacityReservationStatus.HELD)
        self.assertEqual(ticket_type.available_quantity, 2)

    def test_free_event_confirms_capacity_and_issues_individual_access(self):
        ticket_type = self.ticket_type(name="Gratuit", price="0.00", quantity=1)
        order = create_order(
            buyer=self.user,
            event=self.event,
            customer_name="Participant gratuit",
            customer_email=self.user.email,
            selections=[(ticket_type, 1)],
        )
        order.refresh_from_db()
        self.assertEqual(order.status, TicketOrderStatus.CONFIRMED)
        self.assertEqual(order.commerce_order.status, CommerceOrderStatus.CONFIRMED)
        self.assertEqual(order.commerce_order.payment_mode, PaymentMode.NONE)
        reservation = order.items.get().commerce_item.capacity_reservation
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, CapacityReservationStatus.COMMITTED)
        ticket = order.tickets.get()
        self.assertIsNotNone(ticket.access_id)
        self.assertEqual(order.payments.count(), 0)
        self.assertEqual(ticket_type.available_quantity, 0)
