from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessUseResult
from access.services import render_access_credential
from activities.models import OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from capacity.services import InsufficientCapacity
from commerce.models import PaymentMode
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from geography.models import Place, SpacePlace, SpacePlaceRole
from payments.models import PaymentMethod, PaymentProvider, PaymentStatus
from payments.services import complete_payment, initiate_commerce_payment
from scanner.canonical_services import scan_access_credential
from scanner.models import ScannerAssignment
from organizations.models import Organization

from .models import TransportService, Vehicle
from .selectors import departure_capacity_snapshot, departure_manifest, search_departures
from .services import (
    assign_vehicle,
    book_transport,
    cancel_transport_departure,
    configure_transport_fare,
    create_transport_departure,
    create_transport_route,
    create_transport_service,
    publish_transport_departure,
    reschedule_transport_departure,
)


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class TransportCompositionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="traveler",
            email="traveler@example.test",
            password="test-pass-123",
        )
        self.space = Organization.objects.create(
            name="Mulykap",
            slug="mulykap",
            created_by=self.user,
        )
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
        SpacePlace.objects.create(
            organization=self.space,
            place=self.origin,
            role=SpacePlaceRole.BRANCH,
            is_public=True,
        )
        SpacePlace.objects.create(
            organization=self.space,
            place=self.destination,
            role=SpacePlaceRole.BRANCH,
            is_public=True,
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

    def _user(self, suffix):
        return get_user_model().objects.create_user(
            username=f"traveler-{suffix}",
            email=f"traveler-{suffix}@example.test",
            password="test-pass-123",
        )

    def _on_site_offer(self, departure=None, name="Standard", price="20"):
        return configure_transport_fare(
            departure=departure or self.departure,
            name=name,
            unit_price=Decimal(price),
            payment_mode=PaymentMode.ON_SITE,
        )

    def test_transport_is_not_an_event(self):
        self.assertIsInstance(self.service, TransportService)
        self.assertFalse(hasattr(self.service.activity, "event_vertical"))
        self.assertEqual(self.departure.occurrence.activity_id, self.service.activity_id)

    def test_route_uses_places_and_derives_od(self):
        self.assertEqual(self.route.origin, self.origin)
        self.assertEqual(self.route.destination, self.destination)

    def test_route_requires_two_stops(self):
        with self.assertRaises(ValidationError):
            create_transport_route(space=self.space, name="Invalide", stops=[self.origin])

    def test_transport_service_rejects_cross_space_route(self):
        other = Organization.objects.create(name="Autre opérateur", slug="autre", created_by=self.user)
        route = create_transport_route(space=other, name="Autre route", stops=[self.origin, self.destination])
        with self.assertRaises(ValidationError):
            create_transport_service(space=self.space, created_by=self.user, route=route)

    def test_vehicle_caps_commercial_capacity(self):
        small = Vehicle.objects.create(space=self.space, label="Minibus", passenger_capacity=20)
        with self.assertRaises(ValidationError):
            create_transport_departure(
                service=self.service,
                start_at=timezone.now() + timedelta(days=2),
                timezone_name="Africa/Lubumbashi",
                vehicle=small,
                capacity=21,
            )

    def test_inactive_vehicle_is_refused(self):
        vehicle = Vehicle.objects.create(space=self.space, label="Hors service", passenger_capacity=20, active=False)
        with self.assertRaises(ValidationError):
            assign_vehicle(departure=self.departure, vehicle=vehicle)

    def test_two_fares_share_one_pool_and_cannot_oversell(self):
        self.departure.passenger_capacity_pool.total_quantity = 2
        self.departure.passenger_capacity_pool.save(update_fields=["total_quantity", "updated_at"])
        standard = self._on_site_offer(name="Standard", price="20")
        promo = self._on_site_offer(name="Promo", price="15")
        self.assertEqual(standard.capacity_pool_id, promo.capacity_pool_id)
        publish_transport_departure(departure=self.departure)
        book_transport(departure=self.departure, offer=standard, participant=self.user)
        book_transport(departure=self.departure, offer=promo, participant=self._user("two"))
        self.assertTrue(departure_capacity_snapshot(self.departure)["sold_out"])
        with self.assertRaises(InsufficientCapacity):
            book_transport(departure=self.departure, offer=standard, participant=self._user("three"))

    def test_on_site_confirms_without_payment(self):
        offer = self._on_site_offer()
        publish_transport_departure(departure=self.departure)
        result = book_transport(departure=self.departure, offer=offer, participant=self.user)
        result["journey"].refresh_from_db()
        self.assertEqual(result["order"].payment_mode, PaymentMode.ON_SITE)
        self.assertEqual(result["journey"].status, "confirmed")
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
        result = book_transport(departure=self.departure, offer=offer, participant=self.user)
        self.assertIsNotNone(result["access"])
        self.assertFalse(result["order"].payments.exists())

    def test_upfront_payment_confirms_capacity_and_issues_transport_access(self):
        offer = configure_transport_fare(
            departure=self.departure,
            name="Billet web",
            unit_price=Decimal("25"),
            payment_mode=PaymentMode.UPFRONT,
        )
        publish_transport_departure(departure=self.departure)
        result = book_transport(departure=self.departure, offer=offer, participant=self.user)
        result["journey"].refresh_from_db()
        self.assertEqual(result["journey"].status, "pending_payment")
        self.assertIsNone(result["access"])
        payment = initiate_commerce_payment(
            commerce_order=result["order"],
            actor=self.user,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.OTHER,
            idempotency_key="transport-upfront-test",
        )
        with self.captureOnCommitCallbacks(execute=True):
            complete_payment(payment=payment, provider_reference="SBX-TRANSPORT-001", source="test")
        payment.refresh_from_db()
        result["order"].refresh_from_db()
        result["journey"].refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(result["order"].status, "confirmed")
        self.assertEqual(result["journey"].status, "confirmed")
        access = Access.objects.get(journey=result["journey"], source_key="transport-ticket")
        self.assertEqual(access.occurrence_id, self.departure.occurrence_id)

    def test_reassign_smaller_than_consumed_is_refused(self):
        offer = self._on_site_offer()
        publish_transport_departure(departure=self.departure)
        book_transport(departure=self.departure, offer=offer, participant=self.user)
        book_transport(departure=self.departure, offer=offer, participant=self._user("two"))
        self.assertEqual(departure_capacity_snapshot(self.departure)["consumed"], 2)
        too_small = Vehicle.objects.create(space=self.space, label="Minibus trop petit", passenger_capacity=1)
        with self.assertRaises(ValidationError):
            assign_vehicle(departure=self.departure, vehicle=too_small)

    def test_reschedule_updates_occurrence_and_emits_canonical_event(self):
        new_start = timezone.now() + timedelta(days=3)
        reschedule_transport_departure(departure=self.departure, start_at=new_start, end_at=new_start + timedelta(hours=4))
        self.departure.occurrence.refresh_from_db()
        self.assertEqual(self.departure.occurrence.start_at, new_start)
        self.assertTrue(DomainEventOutbox.objects.filter(event_type=DomainEventType.OCCURRENCE_RESCHEDULED, source_id=str(self.departure.occurrence_id)).exists())

    def test_cancelled_departure_disappears_from_public_search(self):
        self._on_site_offer()
        publish_transport_departure(departure=self.departure)
        travel_date = timezone.localtime(self.departure.occurrence.start_at).date()
        self.assertIn(self.departure, list(search_departures(origin=self.origin, destination=self.destination, date=travel_date)))
        cancel_transport_departure(departure=self.departure)
        self.assertEqual(self.departure.occurrence.status, OccurrenceStatus.CANCELLED)
        self.assertNotIn(self.departure, list(search_departures(origin=self.origin, destination=self.destination, date=travel_date)))

    def test_public_search_requires_main_origin_and_destination(self):
        middle = Place.objects.create(name="Likasi", locality="Likasi", country_code="CD", timezone="Africa/Lubumbashi")
        second_route = create_transport_route(space=self.space, name="Lubumbashi → Likasi → Kolwezi", stops=[self.origin, middle, self.destination])
        second_service = create_transport_service(space=self.space, created_by=self.user, route=second_route)
        second_departure = create_transport_departure(service=second_service, start_at=self.departure.occurrence.start_at, timezone_name="Africa/Lubumbashi", capacity=10)
        self._on_site_offer(departure=second_departure)
        publish_transport_departure(departure=second_departure)
        travel_date = timezone.localtime(second_departure.occurrence.start_at).date()
        self.assertIn(second_departure, list(search_departures(origin=self.origin, destination=self.destination, date=travel_date)))
        self.assertNotIn(second_departure, list(search_departures(origin=middle, destination=self.destination, date=travel_date)))

    def test_second_scan_is_already_used_and_wrong_departure_is_refused(self):
        offer = self._on_site_offer()
        publish_transport_departure(departure=self.departure)
        result = book_transport(departure=self.departure, offer=offer, participant=self.user)
        Access.objects.filter(pk=result["access"].pk).update(valid_from=None)
        result["access"].refresh_from_db()
        token = render_access_credential(result["access"].credentials.get(status="active"))
        scanner_user = self._user("scanner")
        ScannerAssignment.objects.create(
            activity=self.service.activity,
            occurrence=self.departure.occurrence,
            agent=scanner_user,
            assigned_by=self.user,
            label="Embarquement",
        )
        first = scan_access_credential(token=token, actor=scanner_user, activity=self.service.activity, occurrence=self.departure.occurrence, source="transport-test")
        second = scan_access_credential(token=token, actor=scanner_user, activity=self.service.activity, occurrence=self.departure.occurrence, source="transport-test")
        self.assertEqual(first.result, AccessUseResult.ACCEPTED)
        self.assertEqual(second.result, AccessUseResult.ALREADY_USED)

        other_departure = create_transport_departure(service=self.service, start_at=timezone.now() + timedelta(days=2), timezone_name="Africa/Lubumbashi", capacity=10)
        ScannerAssignment.objects.create(activity=self.service.activity, occurrence=other_departure.occurrence, agent=self._user("scanner-two"), assigned_by=self.user)
        other_access_user = self._user("ticket-two")
        other_offer = self._on_site_offer(departure=other_departure, name="Second départ")
        publish_transport_departure(departure=other_departure)
        other_result = book_transport(departure=other_departure, offer=other_offer, participant=other_access_user)
        Access.objects.filter(pk=other_result["access"].pk).update(valid_from=None)
        other_result["access"].refresh_from_db()
        other_token = render_access_credential(other_result["access"].credentials.get(status="active"))
        wrong = scan_access_credential(token=other_token, actor=scanner_user, activity=self.service.activity, occurrence=self.departure.occurrence, source="transport-test")
        self.assertEqual(wrong.result, AccessUseResult.WRONG_OCCURRENCE)

    def test_manifest_is_derived_from_access_and_access_use(self):
        offer = self._on_site_offer()
        publish_transport_departure(departure=self.departure)
        result = book_transport(departure=self.departure, offer=offer, participant=self.user)
        rows = departure_manifest(self.departure)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["beneficiary"], self.user)
        self.assertFalse(rows[0]["boarded"])

    def test_login_continuation_returns_to_selected_departure_and_fare(self):
        offer = self._on_site_offer()
        publish_transport_departure(departure=self.departure)
        url = reverse("transport:book", args=[self.departure.pk, offer.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"next={url}", response.url)

    def test_cross_space_console_direct_url_is_forbidden(self):
        owner = self._user("owner")
        grant_space_role(profile=owner, space=self.space, role=SystemRoleCode.SPACE_OWNER, granted_by=self.user)
        other_space = Organization.objects.create(name="Concurrent", slug="concurrent", created_by=self.user)
        self.client.force_login(owner)
        self.assertEqual(self.client.get(reverse("organizations:console-transport", args=[self.space.slug])).status_code, 200)
        self.assertEqual(self.client.get(reverse("organizations:console-transport", args=[other_space.slug])).status_code, 403)

    def test_activity_scoped_manager_sees_only_its_transport_activity(self):
        manager = self._user("activity-manager")
        grant_activity_role(profile=manager, activity=self.service.activity, role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER, granted_by=self.user)
        other_route = create_transport_route(space=self.space, name="Kolwezi → Lubumbashi", stops=[self.destination, self.origin])
        other_service = create_transport_service(space=self.space, created_by=self.user, route=other_route)
        other_departure = create_transport_departure(service=other_service, start_at=timezone.now() + timedelta(days=2), timezone_name="Africa/Lubumbashi", capacity=10)
        self._on_site_offer(departure=other_departure)
        publish_transport_departure(departure=other_departure)
        self._on_site_offer()
        publish_transport_departure(departure=self.departure)
        self.client.force_login(manager)
        response = self.client.get(reverse("organizations:console-transport", args=[self.space.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.route.name)
        self.assertNotContains(response, other_route.name)
