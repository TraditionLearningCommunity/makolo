from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from access.models import AccessStatus, AccessUseResult, CredentialStatus
from access.services import render_access_credential, validate_access_credential
from events.models import Event, EventStatus, EventVisibility
from journeys.models import JourneyStatus, WorkflowKind
from organizations.models import Organization

from .models import TicketOrderStatus, TicketStatus, TicketType
from .services import (
    accept_ticket_transfer,
    cancel_order,
    create_order,
    create_ticket_transfer,
)


User = get_user_model()


class TicketJourneyAccessBridgeTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_superuser(
            username="bridge-organizer",
            email="bridge-organizer@example.com",
            password="Bridge-2026!",
        )
        self.buyer = User.objects.create_user(
            username="bridge-buyer",
            email="bridge-buyer@example.com",
            password="Bridge-2026!",
            first_name="Buyer",
        )
        self.recipient = User.objects.create_user(
            username="bridge-recipient",
            email="bridge-recipient@example.com",
            password="Bridge-2026!",
            first_name="Recipient",
        )
        self.space = Organization.objects.create(
            name="Journey Access Bridge Space",
            created_by=self.organizer,
        )
        start = timezone.now() + timedelta(hours=1)
        self.event = Event.objects.create(
            organizer=self.organizer,
            organization=self.space,
            title="Journey Access Bridge Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=4),
            published_at=timezone.now(),
            capacity=50,
        )
        self.free_type = TicketType.objects.create(
            event=self.event,
            name="Free",
            price=0,
            currency="USD",
            quantity_total=20,
        )

    def _free_order(self):
        return create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name=self.buyer.full_name or self.buyer.username,
            customer_email=self.buyer.email,
            selections=[(self.free_type, 1)],
        )

    def test_free_event_purchase_creates_journey_access_and_credential(self):
        order = self._free_order()
        order.refresh_from_db()
        ticket = order.tickets.select_related("access").get()

        self.assertEqual(order.status, TicketOrderStatus.CONFIRMED)
        self.assertIsNotNone(order.journey_id)
        self.assertEqual(order.journey.workflow, WorkflowKind.PURCHASE)
        self.assertEqual(order.journey.status, JourneyStatus.FULFILLED)
        self.assertIsNotNone(ticket.access_id)
        self.assertEqual(ticket.access.beneficiary_id, self.buyer.pk)
        self.assertEqual(ticket.access.journey_id, order.journey_id)
        self.assertEqual(ticket.access.status, AccessStatus.VALID)
        self.assertEqual(
            ticket.access.credentials.filter(status=CredentialStatus.ACTIVE).count(),
            1,
        )

    def test_paid_pending_order_maps_to_pending_payment_without_ticket(self):
        paid_type = TicketType.objects.create(
            event=self.event,
            name="Paid",
            price="12.00",
            currency="USD",
            quantity_total=20,
        )
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name=self.buyer.username,
            customer_email=self.buyer.email,
            selections=[(paid_type, 1)],
        )
        order.refresh_from_db()
        self.assertEqual(order.status, TicketOrderStatus.PENDING)
        self.assertEqual(order.journey.status, JourneyStatus.PENDING_PAYMENT)
        self.assertFalse(order.tickets.exists())

    def test_transfer_updates_beneficiary_and_rotates_credential(self):
        order = self._free_order()
        ticket = order.tickets.select_related("access").get()
        access = ticket.access
        old_credential = access.credentials.get(status=CredentialStatus.ACTIVE)
        old_token = render_access_credential(old_credential)
        old_code = ticket.code

        transfer = create_ticket_transfer(
            ticket=ticket,
            sender=self.buyer,
            recipient_email=self.recipient.email,
        )
        accept_ticket_transfer(transfer=transfer, recipient=self.recipient)

        ticket.refresh_from_db()
        access.refresh_from_db()
        old_credential.refresh_from_db()
        self.assertEqual(ticket.owner_id, self.recipient.pk)
        self.assertNotEqual(ticket.code, old_code)
        self.assertEqual(access.beneficiary_id, self.recipient.pk)
        self.assertEqual(old_credential.status, CredentialStatus.REVOKED)
        self.assertEqual(
            validate_access_credential(old_token).result,
            AccessUseResult.REVOKED,
        )
        new_credential = access.credentials.get(status=CredentialStatus.ACTIVE)
        self.assertGreater(new_credential.version, old_credential.version)

    def test_cancellation_and_refund_invalidate_access(self):
        order = self._free_order()
        ticket = order.tickets.select_related("access").get()
        old_token = render_access_credential(
            ticket.access.credentials.get(status=CredentialStatus.ACTIVE)
        )
        cancel_order(order=order, actor=self.organizer)
        ticket.refresh_from_db()
        ticket.access.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.CANCELLED)
        self.assertEqual(ticket.access.status, AccessStatus.CANCELLED)
        self.assertEqual(validate_access_credential(old_token).result, AccessUseResult.REVOKED)

        second = self._free_order().tickets.select_related("access").get()
        second.status = TicketStatus.REFUNDED
        second.save(update_fields=["status", "updated_at"])
        second.access.refresh_from_db()
        self.assertEqual(second.access.status, AccessStatus.REVOKED)
        self.assertFalse(second.access.credentials.filter(status=CredentialStatus.ACTIVE).exists())
