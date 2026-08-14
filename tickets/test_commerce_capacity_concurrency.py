from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from events.activity_bridge import sync_event_core
from events.models import Event, EventStatus
from organizations.models import Organization

from .models import TicketType
from .services import create_order


User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Ce test exerce le checkout Event concurrent sur PostgreSQL.")
class EventCommerceCapacityConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.user = User.objects.create_user(username="event-capacity-race", email="event-capacity-race@example.com", password="Capacity-2026!")
        self.space = Organization.objects.create(name="Event Capacity Race", created_by=self.user)
        self.event = Event.objects.create(
            organizer=self.user,
            organization=self.space,
            title="Concert concurrent",
            status=EventStatus.PUBLISHED,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
            registration_start_at=timezone.now() - timedelta(days=1),
            registration_end_at=timezone.now() + timedelta(days=1),
        )
        sync_event_core(self.event)
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Tarif limité",
            price="10.00",
            currency="USD",
            quantity_total=2,
            min_per_order=1,
            max_per_order=1,
            is_active=True,
        )

    def _checkout(self, barrier, number):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            event = Event.objects.get(pk=self.event.pk)
            ticket_type = TicketType.objects.get(pk=self.ticket_type.pk)
            user = User.objects.get(pk=self.user.pk)
            try:
                create_order(
                    buyer=user,
                    event=event,
                    customer_name=f"Participant {number}",
                    customer_email=f"participant-{number}@example.com",
                    selections=[(ticket_type, 1)],
                )
                return "success"
            except ValidationError:
                return "sold_out"
        finally:
            connection.close()

    def test_three_simultaneous_checkouts_get_at_most_two_places(self):
        barrier = Barrier(3)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self._checkout, barrier, number) for number in range(3)]
            results = [future.result(timeout=15) for future in futures]

        self.assertEqual(results.count("success"), 2)
        self.assertEqual(results.count("sold_out"), 1)
