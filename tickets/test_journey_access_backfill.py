from datetime import timedelta
from importlib import import_module

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from access.models import Access, AccessStatus, AccessCredential, AccessUse
from capacity.models import CapacityPool, CapacityReservation
from commerce.models import CommerceOrder, CommerceOrderItem, Offer
from events.activity_bridge import sync_event_core
from events.models import Event, EventStatus, EventVisibility
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .models import Ticket, TicketOrder, TicketOrderItem, TicketOrderStatus, TicketStatus, TicketType


User = get_user_model()
backfill_module = import_module("tickets.migrations.0006_backfill_journey_access")


class JourneyAccessBackfillTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_superuser(
            username="backfill-organizer",
            email="backfill-organizer@example.com",
            password="Backfill-2026!",
        )
        self.buyer = User.objects.create_user(
            username="backfill-buyer",
            email="backfill-buyer@example.com",
            password="Backfill-2026!",
        )
        self.transferred_holder = User.objects.create_user(
            username="backfill-holder",
            email="backfill-holder@example.com",
            password="Backfill-2026!",
        )
        start = timezone.now() + timedelta(days=2)
        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Backfill Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=4),
            published_at=timezone.now(),
            capacity=100,
        )
        # Make the existing Event→Activity compatibility projection explicit in
        # this migration fixture before asserting the canonical Activity FK.
        sync_event_core(self.event)
        self.event.refresh_from_db(fields=["activity"])
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Backfill Ticket",
            price="10.00",
            currency="USD",
            quantity_total=100,
        )

    def _order(self, status):
        return TicketOrder.objects.create(
            event=self.event,
            buyer=self.buyer,
            customer_name="Backfill Buyer",
            customer_email=self.buyer.email,
            status=status,
            total_amount="10.00",
            currency="USD",
        )

    def _ticket(self, order, status, *, owner=None):
        return Ticket.objects.create(
            event=self.event,
            ticket_type=self.ticket_type,
            order=order,
            owner=owner or self.buyer,
            holder_name=(owner or self.buyer).username,
            holder_email=(owner or self.buyer).email,
            status=status,
        )

    def _detach_runtime_bridge(self):
        Ticket.objects.all().update(access=None)

        # Task 7 runtime bridges may already have created canonical Commerce and
        # Capacity projections around these legacy Event rows. This fixture is
        # intentionally simulating the pre-Task-6 database, so detach and remove
        # those newer projections first. Production PROTECT constraints remain
        # unchanged and continue to protect real historical records.
        TicketOrderItem.objects.all().update(commerce_item=None)
        TicketOrder.objects.all().update(commerce_order=None)
        TicketType.objects.all().update(offer=None, capacity_pool=None)
        CommerceOrderItem.objects.all().delete()
        CommerceOrder.objects.all().delete()
        CapacityReservation.objects.all().delete()
        Offer.objects.all().delete()
        CapacityPool.objects.all().delete()

        TicketOrder.objects.all().update(journey=None)
        # Runtime fixtures can already have AccessUse rows through the canonical
        # bridge. The historical-migration simulation must remove those audit
        # rows before deleting Access because AccessUse intentionally PROTECTs
        # its right in production.
        AccessUse.objects.all().delete()
        Access.objects.all().delete()
        Journey.objects.all().delete()

    def _run_backfill(self):
        from django.apps import apps

        backfill_module.backfill_journey_access(apps, None)

    def test_order_status_mapping_and_fulfillment_are_explicit(self):
        pending = self._order(TicketOrderStatus.PENDING)
        confirmed_without_ticket = self._order(TicketOrderStatus.CONFIRMED)
        confirmed_with_ticket = self._order(TicketOrderStatus.CONFIRMED)
        self._ticket(confirmed_with_ticket, TicketStatus.VALID)
        cancelled = self._order(TicketOrderStatus.CANCELLED)
        expired = self._order(TicketOrderStatus.EXPIRED)

        self._detach_runtime_bridge()
        self._run_backfill()

        expected = {
            pending.pk: JourneyStatus.PENDING_PAYMENT,
            confirmed_without_ticket.pk: JourneyStatus.CONFIRMED,
            confirmed_with_ticket.pk: JourneyStatus.FULFILLED,
            cancelled.pk: JourneyStatus.CANCELLED,
            expired.pk: JourneyStatus.EXPIRED,
        }
        for order_id, expected_status in expected.items():
            order = TicketOrder.objects.select_related("journey").get(pk=order_id)
            self.assertIsNotNone(order.journey_id)
            self.assertEqual(order.journey.workflow, WorkflowKind.PURCHASE)
            self.assertEqual(order.journey.status, expected_status)
            self.assertEqual(order.journey.activity_id, self.event.activity_id)
            self.assertEqual(order.journey.beneficiary_id, self.buyer.pk)

    def test_ticket_mapping_uses_real_holder_and_preserves_legacy_qr_strategy(self):
        statuses = (
            (TicketStatus.VALID, AccessStatus.VALID),
            (TicketStatus.USED, AccessStatus.USED),
            (TicketStatus.CANCELLED, AccessStatus.CANCELLED),
            (TicketStatus.REFUNDED, AccessStatus.REVOKED),
        )
        tickets = []
        for index, (ticket_status, _) in enumerate(statuses):
            order = self._order(TicketOrderStatus.CONFIRMED)
            owner = self.transferred_holder if index == 0 else self.buyer
            tickets.append(self._ticket(order, ticket_status, owner=owner))

        self._detach_runtime_bridge()
        self._run_backfill()

        for ticket, (_, expected_status) in zip(tickets, statuses):
            ticket = Ticket.objects.select_related("access", "order__journey").get(pk=ticket.pk)
            self.assertIsNotNone(ticket.access_id)
            self.assertEqual(ticket.access.status, expected_status)
            self.assertEqual(ticket.access.activity_id, self.event.activity_id)
            self.assertEqual(ticket.access.journey_id, ticket.order.journey_id)
            self.assertEqual(ticket.access.valid_until, self.event.end_at)
        transferred = Ticket.objects.select_related("access").get(pk=tickets[0].pk)
        self.assertEqual(transferred.access.beneficiary_id, self.transferred_holder.pk)
        self.assertEqual(AccessCredential.objects.count(), 0)

    def test_backfill_is_idempotent(self):
        order = self._order(TicketOrderStatus.CONFIRMED)
        ticket = self._ticket(order, TicketStatus.VALID)
        self._detach_runtime_bridge()

        self._run_backfill()
        first_journey_id = TicketOrder.objects.get(pk=order.pk).journey_id
        first_access_id = Ticket.objects.get(pk=ticket.pk).access_id
        self._run_backfill()

        self.assertEqual(TicketOrder.objects.get(pk=order.pk).journey_id, first_journey_id)
        self.assertEqual(Ticket.objects.get(pk=ticket.pk).access_id, first_access_id)
        self.assertEqual(Journey.objects.count(), 1)
        self.assertEqual(Access.objects.count(), 1)