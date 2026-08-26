from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from access.models import Access
from commerce.models import CommerceOrder, PaymentMode
from geography.models import Place
from journeys.models import Journey
from organizations.models import Organization

from .models import TransportDeparture, Vehicle
from .services import (
    book_transport,
    configure_transport_fare,
    create_transport_departure,
    create_transport_route,
    create_transport_service,
    publish_transport_departure,
)


User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Ce test exerce l’idempotence Transport PostgreSQL réelle.")
class Task25TransportRetryConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.buyer = User.objects.create_user(
            username="t25-transport-retry-race",
            email="t25-transport-retry-race@example.test",
            password="Transport-2026!",
        )
        space = Organization.objects.create(
            name="T25 Transport Retry Race",
            slug="t25-transport-retry-race",
            created_by=self.buyer,
        )
        origin = Place.objects.create(
            name="Kolwezi Retry Race",
            locality="Kolwezi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
        )
        destination = Place.objects.create(
            name="Lubumbashi Retry Race",
            locality="Lubumbashi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
        )
        route = create_transport_route(
            space=space,
            name="Kolwezi → Lubumbashi Retry Race",
            stops=[origin, destination],
        )
        service = create_transport_service(
            space=space,
            created_by=self.buyer,
            route=route,
        )
        vehicle = Vehicle.objects.create(
            space=space,
            label="Retry Race Bus",
            passenger_capacity=4,
        )
        departure = create_transport_departure(
            service=service,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=4),
            timezone_name="Africa/Lubumbashi",
            vehicle=vehicle,
            capacity=4,
        )
        offer = configure_transport_fare(
            departure=departure,
            name="Retry Race On-site",
            unit_price=Decimal("20.00"),
            payment_mode=PaymentMode.ON_SITE,
        )
        publish_transport_departure(departure=departure)
        self.departure_id = departure.pk
        self.offer_id = offer.pk

    def _book_same_retry(self, barrier):
        close_old_connections()
        try:
            from commerce.models import Offer

            barrier.wait(timeout=5)
            participant = User.objects.get(pk=self.buyer.pk)
            departure = TransportDeparture.objects.get(pk=self.departure_id)
            offer = Offer.objects.get(pk=self.offer_id)
            result = book_transport(
                departure=departure,
                offer=offer,
                participant=participant,
                payment_mode=PaymentMode.ON_SITE,
                idempotency_key="t25-transport-same-network-retry",
            )
            return (
                str(result["journey"].pk),
                str(result["order"].pk),
                str(result["access"].pk),
            )
        finally:
            connection.close()

    def test_two_concurrent_same_key_retries_create_one_business_path(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._book_same_retry, barrier) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]

        self.assertEqual(len(set(results)), 1)
        self.assertEqual(
            CommerceOrder.objects.filter(idempotency_key="t25-transport-same-network-retry").count(),
            1,
        )
        order = CommerceOrder.objects.get(idempotency_key="t25-transport-same-network-retry")
        self.assertEqual(Journey.objects.filter(pk=order.journey_id).count(), 1)
        self.assertEqual(Access.objects.filter(journey_id=order.journey_id, source_key="transport-ticket").count(), 1)
        self.assertEqual(order.items.get().capacity_reservation.quantity, 1)
