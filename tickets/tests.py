from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from events.models import Event, EventStatus, EventVisibility

from .models import TicketOrderStatus, TicketStatus, TicketType
from .services import cancel_order, confirm_order, create_order, validate_qr_token


User = get_user_model()


def make_event(organizer, *, capacity=20):
    start_at = timezone.now() + timedelta(days=5)
    return Event.objects.create(
        organizer=organizer,
        title="Makolo Ticket Test",
        status=EventStatus.PUBLISHED,
        visibility=EventVisibility.PUBLIC,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
        registration_start_at=timezone.now() - timedelta(hours=1),
        registration_end_at=start_at,
        capacity=capacity,
        published_at=timezone.now(),
    )


class TicketServiceTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="ticket-organizer",
            email="organizer-tickets@example.com",
            password="Strong-ticket-password-2026!",
            is_organizer=True,
        )
        self.buyer = User.objects.create_user(
            username="ticket-buyer",
            email="buyer-tickets@example.com",
            password="Strong-ticket-password-2026!",
        )
        self.other = User.objects.create_user(
            username="other-buyer",
            email="other-tickets@example.com",
            password="Strong-ticket-password-2026!",
        )
        self.event = make_event(self.organizer, capacity=5)
        self.free_type = TicketType.objects.create(
            event=self.event,
            name="Entrée gratuite",
            price=Decimal("0.00"),
            quantity_total=3,
            max_per_order=3,
        )
        self.paid_type = TicketType.objects.create(
            event=self.event,
            name="VIP",
            price=Decimal("25.00"),
            quantity_total=2,
            max_per_order=2,
        )

    def test_free_order_is_confirmed_and_issues_tickets(self):
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.free_type, 2)],
        )

        self.assertEqual(order.status, TicketOrderStatus.CONFIRMED)
        self.assertEqual(order.tickets.count(), 2)
        self.free_type.refresh_from_db()
        self.assertEqual(self.free_type.reserved_quantity, 0)
        self.assertEqual(self.free_type.issued_quantity, 2)

    def test_paid_order_reserves_stock_until_confirmation(self):
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.paid_type, 1)],
        )

        self.assertEqual(order.status, TicketOrderStatus.PENDING)
        self.assertEqual(order.tickets.count(), 0)
        self.paid_type.refresh_from_db()
        self.assertEqual(self.paid_type.reserved_quantity, 1)
        self.assertEqual(self.paid_type.issued_quantity, 0)

        confirm_order(order=order, actor=self.organizer)
        order.refresh_from_db()
        self.paid_type.refresh_from_db()
        self.assertEqual(order.status, TicketOrderStatus.CONFIRMED)
        self.assertEqual(order.tickets.count(), 1)
        self.assertEqual(self.paid_type.reserved_quantity, 0)
        self.assertEqual(self.paid_type.issued_quantity, 1)

    def test_buyer_cannot_confirm_paid_order(self):
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.paid_type, 1)],
        )
        with self.assertRaises(PermissionDenied):
            confirm_order(order=order, actor=self.buyer)

    def test_stock_cannot_be_oversold(self):
        create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.paid_type, 2)],
        )
        with self.assertRaises(ValidationError):
            create_order(
                buyer=self.other,
                event=self.event,
                customer_name="Other",
                customer_email=self.other.email,
                selections=[(self.paid_type, 1)],
            )

    def test_event_capacity_is_enforced_across_ticket_types(self):
        create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.free_type, 3), (self.paid_type, 2)],
        )
        extra = TicketType.objects.create(
            event=self.event,
            name="Extra",
            price=0,
            quantity_total=10,
        )
        with self.assertRaises(ValidationError):
            create_order(
                buyer=self.other,
                event=self.event,
                customer_name="Other",
                customer_email=self.other.email,
                selections=[(extra, 1)],
            )

    def test_cancelling_pending_order_releases_reserved_stock(self):
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.paid_type, 2)],
        )
        cancel_order(order=order, actor=self.buyer)
        order.refresh_from_db()
        self.paid_type.refresh_from_db()
        self.assertEqual(order.status, TicketOrderStatus.CANCELLED)
        self.assertEqual(self.paid_type.reserved_quantity, 0)

    def test_qr_token_round_trip_and_tamper_detection(self):
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.free_type, 1)],
        )
        ticket = order.tickets.get()
        validated = validate_qr_token(ticket.qr_token)
        self.assertEqual(validated.pk, ticket.pk)

        with self.assertRaises(ValidationError):
            validate_qr_token(f"{ticket.qr_token}tampered")

    def test_used_ticket_is_not_valid_for_qr_validation(self):
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.free_type, 1)],
        )
        ticket = order.tickets.get()
        token = ticket.qr_token
        ticket.status = TicketStatus.USED
        ticket.used_at = timezone.now()
        ticket.save(update_fields=["status", "used_at", "updated_at"])

        with self.assertRaises(ValidationError):
            validate_qr_token(token)


class TicketApiTests(APITestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="api-organizer",
            email="api-organizer@example.com",
            password="Strong-api-ticket-password-2026!",
            is_organizer=True,
        )
        self.buyer = User.objects.create_user(
            username="api-buyer",
            email="api-buyer@example.com",
            password="Strong-api-ticket-password-2026!",
        )
        self.other = User.objects.create_user(
            username="api-other",
            email="api-other@example.com",
            password="Strong-api-ticket-password-2026!",
        )
        self.event = make_event(self.organizer)
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Standard",
            price=0,
            quantity_total=10,
        )

    def test_anonymous_can_list_public_ticket_types(self):
        response = self.client.get("/api/v1/tickets/types/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_anonymous_cannot_create_order(self):
        response = self.client.post(
            "/api/v1/tickets/orders/",
            {
                "event_id": str(self.event.pk),
                "customer_name": "Anonymous",
                "customer_email": "anonymous@example.com",
                "items": [
                    {"ticket_type_id": str(self.ticket_type.pk), "quantity": 1}
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_create_free_order(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            "/api/v1/tickets/orders/",
            {
                "event_id": str(self.event.pk),
                "customer_name": "API Buyer",
                "customer_email": self.buyer.email,
                "items": [
                    {"ticket_type_id": str(self.ticket_type.pk), "quantity": 1}
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], TicketOrderStatus.CONFIRMED)
        self.assertEqual(len(response.data["tickets"]), 1)

    def test_user_cannot_see_another_users_ticket(self):
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.ticket_type, 1)],
        )
        ticket = order.tickets.get()
        self.client.force_authenticate(self.other)
        response = self.client.get(f"/api/v1/tickets/tickets/{ticket.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_organizer_can_create_ticket_type_for_own_event(self):
        self.client.force_authenticate(self.organizer)
        response = self.client.post(
            "/api/v1/tickets/types/",
            {
                "event_id": str(self.event.pk),
                "name": "Premium",
                "price": "50.00",
                "currency": "USD",
                "quantity_total": 5,
                "min_per_order": 1,
                "max_per_order": 2,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(TicketType.objects.filter(name="Premium").exists())


class TicketWebTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="web-organizer",
            email="web-organizer@example.com",
            password="Strong-web-ticket-password-2026!",
            is_organizer=True,
        )
        self.buyer = User.objects.create_user(
            username="web-buyer",
            email="web-buyer@example.com",
            password="Strong-web-ticket-password-2026!",
        )
        self.event = make_event(self.organizer)
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Web Standard",
            price=0,
            quantity_total=5,
        )

    def test_ticket_list_requires_authentication(self):
        response = self.client.get(reverse("tickets:list"))
        self.assertEqual(response.status_code, 302)

    def test_buyer_can_render_order_form(self):
        self.client.force_login(self.buyer)
        response = self.client.get(
            reverse("tickets:order-create", kwargs={"event_slug": self.event.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Web Standard")
