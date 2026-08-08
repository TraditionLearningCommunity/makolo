from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from events.models import Event, EventStatus, EventVisibility

from .models import (
    TicketStatus,
    TicketTransfer,
    TicketType,
    TransferStatus,
    WaitlistStatus,
)
from .services import (
    accept_ticket_transfer,
    accept_waitlist_offer,
    cancel_order,
    create_order,
    create_ticket_transfer,
    join_waitlist,
    promote_waitlist_for_ticket_type,
    validate_qr_token,
)


User = get_user_model()


def make_event(organizer, *, capacity=10):
    start = timezone.now() + timedelta(days=7)
    return Event.objects.create(
        organizer=organizer,
        title="Makolo Waitlist Transfer Day",
        status=EventStatus.PUBLISHED,
        visibility=EventVisibility.PUBLIC,
        start_at=start,
        end_at=start + timedelta(hours=4),
        registration_start_at=timezone.now() - timedelta(hours=1),
        registration_end_at=start,
        capacity=capacity,
        published_at=timezone.now(),
    )


class SmartWaitlistServiceTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="waitlist-organizer",
            email="waitlist-organizer@example.com",
            password="StrongPass2026!",
            is_organizer=True,
        )
        self.owner = User.objects.create_user(
            username="seat-owner",
            email="seat-owner@example.com",
            password="StrongPass2026!",
        )
        self.waiter = User.objects.create_user(
            username="first-waiter",
            email="first-waiter@example.com",
            password="StrongPass2026!",
        )
        self.second_waiter = User.objects.create_user(
            username="second-waiter",
            email="second-waiter@example.com",
            password="StrongPass2026!",
        )
        self.event = make_event(self.organizer, capacity=1)
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Unique Seat",
            price=Decimal("0.00"),
            quantity_total=1,
            max_per_order=1,
        )
        self.owner_order = create_order(
            buyer=self.owner,
            event=self.event,
            customer_name="Seat Owner",
            customer_email=self.owner.email,
            selections=[(self.ticket_type, 1)],
        )

    def test_user_can_join_only_when_sold_out_and_duplicate_is_idempotent(self):
        first = join_waitlist(user=self.waiter, ticket_type=self.ticket_type, quantity=1)
        duplicate = join_waitlist(user=self.waiter, ticket_type=self.ticket_type, quantity=1)

        self.assertEqual(first.pk, duplicate.pk)
        self.assertEqual(first.status, WaitlistStatus.WAITING)

    def test_fifo_promotion_creates_temporary_order(self):
        first = join_waitlist(user=self.waiter, ticket_type=self.ticket_type, quantity=1)
        second = join_waitlist(user=self.second_waiter, ticket_type=self.ticket_type, quantity=1)

        with self.captureOnCommitCallbacks(execute=True):
            cancel_order(order=self.owner_order, actor=self.organizer)

        first.refresh_from_db()
        second.refresh_from_db()
        self.ticket_type.refresh_from_db()

        self.assertEqual(first.status, WaitlistStatus.OFFERED)
        self.assertIsNotNone(first.offered_order_id)
        self.assertEqual(second.status, WaitlistStatus.WAITING)
        self.assertEqual(self.ticket_type.reserved_quantity, 1)

    def test_free_waitlist_offer_is_confirmed_only_after_acceptance(self):
        entry = join_waitlist(user=self.waiter, ticket_type=self.ticket_type, quantity=1)
        cancel_order(order=self.owner_order, actor=self.organizer)
        promote_waitlist_for_ticket_type(self.ticket_type.pk)
        entry.refresh_from_db()

        order = entry.offered_order
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.tickets.count(), 0)

        accept_waitlist_offer(entry=entry, user=self.waiter)
        entry.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(entry.status, WaitlistStatus.CONVERTED)
        self.assertEqual(order.status, "confirmed")
        self.assertEqual(order.tickets.count(), 1)

    def test_waitlist_cannot_be_used_while_stock_is_available(self):
        cancel_order(order=self.owner_order, actor=self.organizer)
        with self.assertRaises(ValidationError):
            join_waitlist(user=self.waiter, ticket_type=self.ticket_type, quantity=1)


class SecureTicketTransferServiceTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="transfer-organizer",
            email="transfer-organizer@example.com",
            password="StrongPass2026!",
            is_organizer=True,
        )
        self.sender = User.objects.create_user(
            username="transfer-sender",
            email="transfer-sender@example.com",
            password="StrongPass2026!",
        )
        self.recipient = User.objects.create_user(
            username="transfer-recipient",
            email="transfer-recipient@example.com",
            password="StrongPass2026!",
        )
        self.other = User.objects.create_user(
            username="transfer-other",
            email="transfer-other@example.com",
            password="StrongPass2026!",
        )
        self.event = make_event(self.organizer)
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Transfer Pass",
            price=Decimal("0.00"),
            quantity_total=5,
        )
        order = create_order(
            buyer=self.sender,
            event=self.event,
            customer_name="Transfer Sender",
            customer_email=self.sender.email,
            selections=[(self.ticket_type, 1)],
        )
        self.ticket = order.tickets.get()

    def test_accepting_transfer_rotates_qr_and_changes_owner(self):
        old_token = self.ticket.qr_token
        old_code = self.ticket.code
        transfer = create_ticket_transfer(
            ticket=self.ticket,
            sender=self.sender,
            recipient_email=self.recipient.email,
        )

        accept_ticket_transfer(transfer=transfer, recipient=self.recipient)
        transfer.refresh_from_db()
        self.ticket.refresh_from_db()

        self.assertEqual(transfer.status, TransferStatus.ACCEPTED)
        self.assertEqual(self.ticket.owner, self.recipient)
        self.assertNotEqual(self.ticket.code, old_code)
        self.assertEqual(validate_qr_token(self.ticket.qr_token).pk, self.ticket.pk)
        with self.assertRaises(ValidationError):
            validate_qr_token(old_token)

    def test_non_owner_cannot_create_transfer(self):
        with self.assertRaises(PermissionDenied):
            create_ticket_transfer(
                ticket=self.ticket,
                sender=self.other,
                recipient_email=self.recipient.email,
            )

    def test_only_recipient_can_accept_transfer(self):
        transfer = create_ticket_transfer(
            ticket=self.ticket,
            sender=self.sender,
            recipient_email=self.recipient.email,
        )
        with self.assertRaises(PermissionDenied):
            accept_ticket_transfer(transfer=transfer, recipient=self.other)

    def test_used_ticket_cannot_be_transferred(self):
        self.ticket.status = TicketStatus.USED
        self.ticket.used_at = timezone.now()
        self.ticket.save(update_fields=["status", "used_at", "updated_at"])
        with self.assertRaises(ValidationError):
            create_ticket_transfer(
                ticket=self.ticket,
                sender=self.sender,
                recipient_email=self.recipient.email,
            )

    def test_recipient_must_have_makolo_account(self):
        with self.assertRaises(ValidationError):
            create_ticket_transfer(
                ticket=self.ticket,
                sender=self.sender,
                recipient_email="unknown@example.com",
            )


class WaitlistTransferApiTests(APITestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="api-wt-organizer",
            email="api-wt-organizer@example.com",
            password="StrongPass2026!",
            is_organizer=True,
        )
        self.owner = User.objects.create_user(
            username="api-wt-owner",
            email="api-wt-owner@example.com",
            password="StrongPass2026!",
        )
        self.waiter = User.objects.create_user(
            username="api-wt-waiter",
            email="api-wt-waiter@example.com",
            password="StrongPass2026!",
        )
        self.recipient = User.objects.create_user(
            username="api-wt-recipient",
            email="api-wt-recipient@example.com",
            password="StrongPass2026!",
        )
        self.event = make_event(self.organizer, capacity=1)
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="API One Seat",
            price=0,
            quantity_total=1,
        )
        self.order = create_order(
            buyer=self.owner,
            event=self.event,
            customer_name="Owner",
            customer_email=self.owner.email,
            selections=[(self.ticket_type, 1)],
        )
        self.ticket = self.order.tickets.get()

    def test_waitlist_api_join(self):
        self.client.force_authenticate(self.waiter)
        response = self.client.post(
            "/api/v1/tickets/waitlist/",
            {"ticket_type_id": str(self.ticket_type.pk), "quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], WaitlistStatus.WAITING)

    def test_transfer_api_create_and_accept(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            "/api/v1/tickets/transfers/",
            {
                "ticket_id": str(self.ticket.pk),
                "recipient_email": self.recipient.email,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        transfer_id = response.data["id"]

        self.client.force_authenticate(self.recipient)
        response = self.client.post(
            f"/api/v1/tickets/transfers/{transfer_id}/accept/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], TransferStatus.ACCEPTED)
        self.assertEqual(TicketTransfer.objects.get(pk=transfer_id).status, TransferStatus.ACCEPTED)
