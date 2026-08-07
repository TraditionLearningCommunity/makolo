from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from events.models import Event, EventStatus, EventVisibility

from .models import TicketType
from .services import cancel_order, create_order


User = get_user_model()


def make_private_event(organizer):
    start_at = timezone.now() + timedelta(days=3)
    return Event.objects.create(
        organizer=organizer,
        title="Private ticket event",
        status=EventStatus.PUBLISHED,
        visibility=EventVisibility.PRIVATE,
        start_at=start_at,
        end_at=start_at + timedelta(hours=2),
        registration_start_at=timezone.now() - timedelta(hours=1),
        registration_end_at=start_at,
        published_at=timezone.now(),
    )


class TicketSecurityApiTests(APITestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="private-organizer",
            email="private-organizer@example.com",
            password="Strong-private-ticket-password-2026!",
            is_organizer=True,
        )
        self.participant = User.objects.create_user(
            username="private-participant",
            email="private-participant@example.com",
            password="Strong-private-ticket-password-2026!",
        )
        self.event = make_private_event(self.organizer)
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Private type",
            price=0,
            quantity_total=5,
        )

    def test_participant_cannot_order_private_event_through_api(self):
        self.client.force_authenticate(self.participant)
        response = self.client.post(
            "/api/v1/tickets/orders/",
            {
                "event_id": str(self.event.pk),
                "customer_name": "Participant",
                "customer_email": self.participant.email,
                "items": [
                    {"ticket_type_id": str(self.ticket_type.pk), "quantity": 1}
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("event_id", response.data)

    def test_participant_cannot_open_private_web_order_page(self):
        self.client.force_login(self.participant)
        response = self.client.get(
            reverse("tickets:order-create", kwargs={"event_slug": self.event.slug})
        )
        self.assertEqual(response.status_code, 404)


class ConfirmedOrderCancellationTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="cancel-organizer",
            email="cancel-organizer@example.com",
            password="Strong-cancel-ticket-password-2026!",
            is_organizer=True,
        )
        self.buyer = User.objects.create_user(
            username="cancel-buyer",
            email="cancel-buyer@example.com",
            password="Strong-cancel-ticket-password-2026!",
        )
        start_at = timezone.now() + timedelta(days=2)
        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Cancellation event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
            registration_start_at=timezone.now() - timedelta(hours=1),
            registration_end_at=start_at,
            published_at=timezone.now(),
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Free confirmed",
            price=0,
            quantity_total=5,
        )

    def test_buyer_cannot_cancel_confirmed_order(self):
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.ticket_type, 1)],
        )
        with self.assertRaises(PermissionDenied):
            cancel_order(order=order, actor=self.buyer)

    def test_organizer_can_cancel_confirmed_unused_order(self):
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(self.ticket_type, 1)],
        )
        cancel_order(order=order, actor=self.organizer)
        order.refresh_from_db()
        self.ticket_type.refresh_from_db()
        self.assertEqual(order.status, "cancelled")
        self.assertEqual(self.ticket_type.issued_quantity, 0)
