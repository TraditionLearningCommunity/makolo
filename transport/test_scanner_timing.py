from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from access.models import AccessUseResult
from access.services import render_access_credential
from commerce.models import PaymentMode
from geography.models import Place
from organizations.models import Organization
from scanner.canonical_services import scan_access_credential
from scanner.models import ScannerAssignment

from .services import (
    book_transport,
    configure_transport_fare,
    create_transport_departure,
    create_transport_route,
    create_transport_service,
    create_transport_vehicle,
    publish_transport_departure,
)


class TransportScannerTimingTests(TestCase):
    def test_future_ticket_is_rejected_then_accepts_at_departure_and_second_scan_is_used(self):
        User = get_user_model()
        traveler = User.objects.create_user(
            username="transport-timing-traveler",
            email="transport-timing-traveler@example.test",
            password="test-pass-123",
        )
        scanner = User.objects.create_user(
            username="transport-timing-scanner",
            email="transport-timing-scanner@example.test",
            password="test-pass-123",
        )
        space = Organization.objects.create(
            name="Transport Timing Space",
            slug="transport-timing-space",
            created_by=traveler,
        )
        origin = Place.objects.create(
            name="Timing Origin",
            locality="Lubumbashi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
        )
        destination = Place.objects.create(
            name="Timing Destination",
            locality="Kolwezi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
        )
        route = create_transport_route(
            space=space,
            name="Timing Route",
            stops=[origin, destination],
        )
        service = create_transport_service(
            space=space,
            created_by=traveler,
            route=route,
        )
        vehicle = create_transport_vehicle(
            space=space,
            label="Timing Coach",
            passenger_capacity=10,
        )
        start_at = timezone.now() + timedelta(days=1)
        departure = create_transport_departure(
            service=service,
            start_at=start_at,
            end_at=start_at + timedelta(hours=4),
            timezone_name="Africa/Lubumbashi",
            vehicle=vehicle,
            capacity=10,
        )
        offer = configure_transport_fare(
            departure=departure,
            name="Timing Fare",
            unit_price=Decimal("20.00"),
            payment_mode=PaymentMode.ON_SITE,
        )
        publish_transport_departure(departure=departure)
        booking = book_transport(
            departure=departure,
            offer=offer,
            participant=traveler,
        )
        access = booking["access"]
        token = render_access_credential(access.credentials.get(status="active"))
        ScannerAssignment.objects.create(
            activity=service.activity,
            occurrence=departure.occurrence,
            agent=scanner,
            assigned_by=traveler,
            label="Timing boarding",
        )

        early = scan_access_credential(
            token=token,
            actor=scanner,
            activity=service.activity,
            occurrence=departure.occurrence,
            source="transport-timing-test",
        )
        self.assertEqual(early.result, AccessUseResult.NOT_YET_VALID)

        boarding_time = departure.occurrence.start_at + timedelta(minutes=1)
        accepted = scan_access_credential(
            token=token,
            actor=scanner,
            activity=service.activity,
            occurrence=departure.occurrence,
            source="transport-timing-test",
            now=boarding_time,
        )
        second = scan_access_credential(
            token=token,
            actor=scanner,
            activity=service.activity,
            occurrence=departure.occurrence,
            source="transport-timing-test",
            now=boarding_time + timedelta(minutes=1),
        )

        self.assertEqual(accepted.result, AccessUseResult.ACCEPTED)
        self.assertEqual(second.result, AccessUseResult.ALREADY_USED)
