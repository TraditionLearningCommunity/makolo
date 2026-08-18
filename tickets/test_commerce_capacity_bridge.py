from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.test import TestCase
from django.utils import timezone

from access.models import CredentialStatus
from capacity.models import CapacityReservationStatus
from commerce.models import CommerceOrderStatus, PaymentMode
from commerce.services import update_offer
from events.models import Event, EventStatus
from organizations.models import Organization

from .models import TicketOrderStatus, TicketType
from .services import create_order


class EventCommerceCapacityVerticalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="event-commerce-vertical",
            email="event-commerce-vertical@example.com",
            password="Commerce-2026!",
        )
        self.space = Organization.objects.create(name="Event Commerce", created_by=self.user)
        self.event = Event.objects.create(
            organizer=self.user,
            organization=self.space,
            title="Concert vertical",
            status=EventStatus.PUBLISHED,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
            registration_start_at=timezone.now() - timedelta(days=1),
            registration_end_at=timezone.now() + timedelta(days=1),
        )

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

    def test_ticket_type_has_no_commercial_storage_and_reads_offer_capacity(self):
        ticket_type = self.ticket_type()
        for removed_field in (
            "price", "currency", "quantity_total", "reserved_quantity", "issued_quantity",
            "sales_start_at", "sales_end_at", "min_per_order", "max_per_order", "is_active",
        ):
            with self.assertRaises(FieldDoesNotExist):
                TicketType._meta.get_field(removed_field)

        update_offer(offer=ticket_type.offer, unit_price=Decimal("30.00"), currency="CDF")
        ticket_type.offer.refresh_from_db()
        self.assertEqual(ticket_type.price, Decimal("30.00"))
        self.assertEqual(ticket_type.currency, "CDF")

        ticket_type.capacity_pool.total_quantity = 6
        ticket_type.capacity_pool.save(update_fields=["total_quantity", "updated_at"])
        self.assertEqual(ticket_type.quantity_total, 6)
        self.assertEqual(ticket_type.available_quantity, 6)

    def test_paid_event_order_creates_journey_commerce_and_capacity_hold(self):
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
        self.assertEqual(order.tickets.count(), 0)
        self.assertEqual(order.payments.count(), 0)

        item = order.items.get()
        self.assertIsNotNone(item.commerce_item_id)
        self.assertEqual(item.commerce_item.capacity_reservation.status, CapacityReservationStatus.HELD)
        self.assertEqual(ticket_type.available_quantity, 2)

    def test_free_event_commits_capacity_issues_access_qr_without_payment(self):
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

        ticket = order.tickets.select_related("access").get()
        self.assertIsNotNone(ticket.access_id)
        credential = ticket.access.credentials.get(status=CredentialStatus.ACTIVE)
        self.assertIn(str(credential.public_id), ticket.qr_token)
        self.assertEqual(order.payments.count(), 0)
        self.assertEqual(ticket_type.available_quantity, 0)

    def test_sold_out_is_decided_by_capacity_pool(self):
        ticket_type = self.ticket_type(quantity=1)
        create_order(
            buyer=self.user,
            event=self.event,
            customer_name="Premier",
            customer_email=self.user.email,
            selections=[(ticket_type, 1)],
        )
        with self.assertRaises(ValidationError):
            create_order(
                buyer=self.user,
                event=self.event,
                customer_name="Deuxième",
                customer_email=self.user.email,
                selections=[(ticket_type, 1)],
            )
