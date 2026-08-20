from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from commerce.models import PaymentMode
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization

from .models import CapacityPool
from .services import InsufficientCapacity, reserve_capacity


User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Ce test exerce le verrouillage PostgreSQL réel.")
class CapacityConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.user = User.objects.create_user(username="capacity-concurrency", email="capacity-concurrency@example.com", password="Capacity-2026!")
        self.space = Organization.objects.create(name="Concurrent Capacity", created_by=self.user)
        self.activity = Activity.objects.create(space=self.space, created_by=self.user, title="Capacité concurrente")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=1),
        )
        self.pool = CapacityPool.objects.create(activity=self.activity, occurrence=self.occurrence, total_quantity=1)
        self.journey_ids = [
            create_journey(
                initiated_by=self.user,
                beneficiary=self.user,
                activity=self.activity,
                occurrence=self.occurrence,
                workflow=WorkflowKind.REGISTRATION,
            ).pk
            for _ in range(2)
        ]

    def _reserve(self, barrier, journey_id):
        close_old_connections()
        try:
            from journeys.models import Journey

            barrier.wait(timeout=5)
            journey = Journey.objects.get(pk=journey_id)
            pool = CapacityPool.objects.get(pk=self.pool.pk)
            try:
                reserve_capacity(pool=pool, journey=journey, quantity=1, source_key=f"race:{journey_id}")
                return "success"
            except InsufficientCapacity:
                return "insufficient_capacity"
        finally:
            connection.close()

    def test_two_simultaneous_holds_never_oversell_one_place(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._reserve, barrier, journey_id) for journey_id in self.journey_ids]
            results = [future.result(timeout=10) for future in futures]

        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("insufficient_capacity"), 1)


@skipUnless(connection.vendor == "postgresql", "Ce test exerce l’intégration Transport/Capacity PostgreSQL réelle.")
class TransportCapacityConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        from geography.models import Place
        from transport.services import (
            configure_transport_fare,
            create_transport_departure,
            create_transport_route,
            create_transport_service,
            publish_transport_departure,
        )

        self.owner = User.objects.create_user(username="transport-race-owner", email="transport-race-owner@example.com", password="Capacity-2026!")
        self.participants = [
            User.objects.create_user(username=f"transport-race-{index}", email=f"transport-race-{index}@example.com", password="Capacity-2026!")
            for index in range(2)
        ]
        self.space = Organization.objects.create(name="Transport Race", created_by=self.owner)
        origin = Place.objects.create(name="Lubumbashi Race", locality="Lubumbashi", country_code="CD", timezone="Africa/Lubumbashi")
        destination = Place.objects.create(name="Kolwezi Race", locality="Kolwezi", country_code="CD", timezone="Africa/Lubumbashi")
        route = create_transport_route(space=self.space, name="Lubumbashi Race → Kolwezi Race", stops=[origin, destination])
        service = create_transport_service(space=self.space, created_by=self.owner, route=route)
        departure = create_transport_departure(
            service=service,
            start_at=timezone.now() + timedelta(days=1),
            timezone_name="Africa/Lubumbashi",
            capacity=1,
        )
        offer = configure_transport_fare(
            departure=departure,
            name="Standard",
            unit_price=Decimal("10"),
            payment_mode=PaymentMode.ON_SITE,
        )
        publish_transport_departure(departure=departure)
        self.departure_id = departure.pk
        self.offer_id = offer.pk

    def _book(self, barrier, participant_id):
        close_old_connections()
        try:
            from commerce.models import Offer
            from transport.models import TransportDeparture
            from transport.services import book_transport

            barrier.wait(timeout=5)
            participant = User.objects.get(pk=participant_id)
            departure = TransportDeparture.objects.get(pk=self.departure_id)
            offer = Offer.objects.get(pk=self.offer_id)
            try:
                book_transport(departure=departure, offer=offer, participant=participant)
                return "success"
            except InsufficientCapacity:
                return "insufficient_capacity"
        finally:
            connection.close()

    def test_two_transport_bookings_never_oversell_one_place(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._book, barrier, participant.pk) for participant in self.participants]
            results = [future.result(timeout=15) for future in futures]

        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("insufficient_capacity"), 1)
