from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from commerce.models import PaymentMode
from geography.models import Place
from organizations.models import Organization

from .models import TransportService, Vehicle
from .selectors import departure_capacity_snapshot
from .services import (
    assign_vehicle,
    book_transport,
    configure_transport_fare,
    create_transport_departure,
    create_transport_route,
    create_transport_service,
    publish_transport_departure,
)


class TransportCompositionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="traveler",
            email="traveler@example.test",
            password="test-pass-123",
        )
        self.space = Organization.objects.create(name="Mulykap", slug="mulykap")
        self.origin = Place.objects.create(
            name="Agence Lubumbashi",
            locality="Lubumbashi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
        )
        self.destination = Place.objects.create(
            name="Agence Kolwezi",
            locality="Kolwezi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
        )
        self.route = create_transport_route(
            space=self.space,
            name="Lubumbashi → Kolwezi",
            stops=[self.origin, self.destination],
        )
        self.service = create_transport_service(
            space=self.space,
            created_by=self.user,
            route=self.route,
        )
        self.vehicle = Vehicle.objects.create(
            space=self.space,
            label="Autocar 52",
            passenger_capacity=52,
        )
        self.departure = create_transport_departure(
            service=self.service,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=4),
            timezone_name="Africa/Lubumbashi",
            vehicle=self.vehicle,
            capacity=52,
        )

    def test_transport_is_not_an_event(self):
        self.assertIsInstance(self.service, TransportService)
        self.assertFalse(hasattr(self.service.activity, "event_vertical"))
        self.assertEqual(self.departure.occurrence.activity_id, self.service.activity_id)

    def test_route_uses_places_and_derives_od(self):
        self.assertEqual(self.route.origin, self.origin)
        self.assertEqual(self.route.destination, self.destination)

    def test_vehicle_caps_commercial_capacity(self):
        small = Vehicle.objects.create(
            space=self.space,
            label="Minibus",
            passenger_capacity=20,
        )
        with self.assertRaises(ValidationError):
            create_transport_departure(
                service=self.service,
                start_at=timezone.now() + timedelta(days=2),
                timezone_name="Africa/Lubumbashi",
                vehicle=small,
                capacity=21,
            )

    def test_two_fares_share_one_pool(self):
        standard = configure_transport_fare(
            departure=self.departure,
            name="Standard",
            unit_price=Decimal("20"),
            payment_mode=PaymentMode.ON_SITE,
        )
        promo = configure_transport_fare(
            departure=self.departure,
            name="Promo",
            unit_price=Decimal("15"),
            payment_mode=PaymentMode.ON_SITE,
        )
        self.assertEqual(standard.capacity_pool_id, promo.capacity_pool_id)

    def test_on_site_confirms_without_payment(self):
        offer = configure_transport_fare(
            departure=self.departure,
            name="Réserver",
            unit_price=Decimal("20"),
            payment_mode=PaymentMode.ON_SITE,
        )
        publish_transport_departure(departure=self.departure)
        result = book_transport(
            departure=self.departure,
            offer=offer,
            participant=self.user,
        )
        self.assertEqual(result["order"].payment_mode, PaymentMode.ON_SITE)
        self.assertIsNotNone(result["access"])
        self.assertFalse(result["order"].payments.exists())

    def test_free_transport_has_no_payment(self):
        offer = configure_transport_fare(
            departure=self.departure,
            name="Navette gratuite",
            unit_price=Decimal("0"),
            payment_mode=PaymentMode.NONE,
        )
        publish_transport_departure(departure=self.departure)
        result = book_transport(
            departure=self.departure,
            offer=offer,
            participant=self.user,
        )
        self.assertIsNotNone(result["access"])
        self.assertFalse(result["order"].payments.exists())

    def test_reassign_smaller_than_consumed_is_refused(self):
        User = get_user_model()
        second_user = User.objects.create_user(
            username="traveler-two",
            email="traveler-two@example.test",
            password="test-pass-123",
        )
        offer = configure_transport_fare(
            departure=self.departure,
            name="Réserver",
            unit_price=Decimal("20"),
            payment_mode=PaymentMode.ON_SITE,
        )
        publish_transport_departure(departure=self.departure)
        book_transport(departure=self.departure, offer=offer, participant=self.user)
        book_transport(departure=self.departure, offer=offer, participant=second_user)

        self.assertEqual(departure_capacity_snapshot(self.departure)["consumed"], 2)
        too_small = Vehicle.objects.create(
            space=self.space,
            label="Minibus trop petit",
            passenger_capacity=1,
        )
        with self.assertRaises(ValidationError):
            assign_vehicle(departure=self.departure, vehicle=too_small)
