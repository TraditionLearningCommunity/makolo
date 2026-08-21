from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from activities.models import (
    Activity,
    ActivityStatus,
    ActivityVisibility,
    Occurrence,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
)
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from commerce.models import Offer, OfferStatus, PaymentMode
from events.models import Event, EventCategory
from geography.models import Place, SpacePlace, SpacePlaceRole
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, OrganizationVerificationStatus
from transport.services import (
    configure_transport_fare,
    create_transport_departure,
    create_transport_route,
    create_transport_service,
    publish_transport_departure,
)

from .models import EventBookmark
from .search import search_occurrences


User = get_user_model()
LUB = ZoneInfo("Africa/Lubumbashi")
UTC = ZoneInfo("UTC")


class CanonicalDiscoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="discovery-owner",
            email="discovery-owner@example.test",
            password="StrongPass2026!",
        )
        self.participant = User.objects.create_user(
            username="discovery-participant",
            email="discovery-participant@example.test",
            password="StrongPass2026!",
        )
        self.space = Organization.objects.create(
            name="Makolo Discovery Space",
            slug="makolo-discovery-space",
            city="Lubumbashi",
            country="CD",
            public_profile=True,
            verification_status=OrganizationVerificationStatus.VERIFIED,
            created_by=self.user,
        )
        self.category = EventCategory.objects.create(name="Culture Discovery")
        self.lubumbashi = Place.objects.create(
            name="Maison Makolo Lubumbashi",
            locality="Lubumbashi",
            country_code="CD",
            latitude=Decimal("-11.664700"),
            longitude=Decimal("27.479400"),
            timezone="Africa/Lubumbashi",
            created_by=self.user,
        )
        self.kolwezi = Place.objects.create(
            name="Agence Makolo Kolwezi",
            locality="Kolwezi",
            country_code="CD",
            latitude=Decimal("-10.716700"),
            longitude=Decimal("25.466700"),
            timezone="Africa/Lubumbashi",
            created_by=self.user,
        )
        SpacePlace.objects.create(
            organization=self.space,
            place=self.lubumbashi,
            role=SpacePlaceRole.SERVICE_POINT,
            is_public=True,
        )
        self.now = datetime(2026, 8, 20, 10, 0, tzinfo=LUB)
        now_patcher = patch("discovery.search.timezone.now", return_value=self.now)
        now_patcher.start()
        self.addCleanup(now_patcher.stop)

    def _occurrence(
        self,
        title,
        *,
        start,
        end=None,
        place=None,
        visibility=ActivityVisibility.PUBLIC,
        activity_status=ActivityStatus.PUBLISHED,
        occurrence_status=OccurrenceStatus.SCHEDULED,
        timezone_name="Africa/Lubumbashi",
        space=None,
    ):
        activity = Activity.objects.create(
            space=space or self.space,
            created_by=self.user,
            title=title,
            short_description=f"Résumé {title}",
            description=f"Description publique de {title}",
            status=activity_status,
            visibility=visibility,
        )
        occurrence = Occurrence.objects.create(
            activity=activity,
            start_at=start,
            end_at=end or start + timedelta(hours=2),
            timezone=timezone_name,
            status=occurrence_status,
        )
        if place:
            OccurrencePlace.objects.create(
                occurrence=occurrence,
                place=place,
                role=OccurrencePlaceRole.PRIMARY,
            )
        return activity, occurrence

    def _event(self, title, *, start, place=None, price=None, visibility=ActivityVisibility.PUBLIC):
        activity, occurrence = self._occurrence(
            title,
            start=start,
            place=place,
            visibility=visibility,
        )
        event = Event.objects.create(
            activity=activity,
            category=self.category,
            published_at=self.now,
        )
        offer = None
        pool = None
        if price is not None:
            pool = CapacityPool.objects.create(
                activity=activity,
                occurrence=occurrence,
                label="Participation",
                total_quantity=20,
            )
            price = Decimal(str(price))
            offer = Offer.objects.create(
                activity=activity,
                occurrence=occurrence,
                capacity_pool=pool,
                name="Standard",
                unit_price=price,
                currency="USD",
                payment_mode=PaymentMode.NONE if price == 0 else PaymentMode.UPFRONT,
                status=OfferStatus.ACTIVE,
            )
        return event, occurrence, offer, pool

    def _transport(self, *, start):
        SpacePlace.objects.get_or_create(
            organization=self.space,
            place=self.kolwezi,
            role=SpacePlaceRole.SERVICE_POINT,
            defaults={"is_public": True},
        )
        route = create_transport_route(
            space=self.space,
            name="Lubumbashi → Kolwezi Discovery",
            stops=[self.lubumbashi, self.kolwezi],
        )
        service = create_transport_service(
            space=self.space,
            created_by=self.user,
            route=route,
            title="Trajet Lubumbashi Kolwezi",
        )
        departure = create_transport_departure(
            service=service,
            start_at=start,
            end_at=start + timedelta(hours=4),
            timezone_name="Africa/Lubumbashi",
            capacity=30,
        )
        configure_transport_fare(
            departure=departure,
            name="Tarif Discovery",
            unit_price=Decimal("15.00"),
            payment_mode=PaymentMode.UPFRONT,
        )
        publish_transport_departure(departure=departure)
        return service, departure

    def test_visibility_and_status_are_canonical(self):
        public, public_occ = self._occurrence(
            "Public", start=self.now + timedelta(hours=3), place=self.lubumbashi
        )
        self._occurrence(
            "Unlisted",
            start=self.now + timedelta(hours=4),
            place=self.lubumbashi,
            visibility=ActivityVisibility.UNLISTED,
        )
        self._occurrence(
            "Private",
            start=self.now + timedelta(hours=5),
            place=self.lubumbashi,
            visibility=ActivityVisibility.PRIVATE,
        )
        self._occurrence(
            "Cancelled activity",
            start=self.now + timedelta(hours=6),
            place=self.lubumbashi,
            activity_status=ActivityStatus.CANCELLED,
        )
        self._occurrence(
            "Cancelled occurrence",
            start=self.now + timedelta(hours=7),
            place=self.lubumbashi,
            occurrence_status=OccurrenceStatus.CANCELLED,
        )
        result = search_occurrences({}, now=self.now)
        self.assertEqual([item.occurrence_id for item in result.items], [str(public_occ.pk)])
        self.assertEqual(result.items[0].activity_id, str(public.pk))

    def test_event_and_transport_share_one_engine_without_event_for_transport(self):
        event, event_occ, _, _ = self._event(
            "Festival Discovery",
            start=self.now + timedelta(days=1),
            place=self.lubumbashi,
            price="10.00",
        )
        service, departure = self._transport(start=self.now + timedelta(days=1, hours=1))
        self.assertFalse(hasattr(service.activity, "event_vertical"))
        result = search_occurrences({"place": "Lubumbashi"}, now=self.now)
        by_occurrence = {item.occurrence_id: item for item in result.items}
        self.assertEqual(by_occurrence[str(event_occ.pk)].vertical, "event")
        self.assertEqual(by_occurrence[str(departure.occurrence_id)].vertical, "transport")
        self.assertEqual(by_occurrence[str(event_occ.pk)].url, reverse("events:detail", args=[event.slug]))
        self.assertEqual(
            by_occurrence[str(departure.occurrence_id)].url,
            reverse("transport:departure-detail", args=[departure.pk]),
        )

    def test_today_tomorrow_weekend_exact_and_range_use_occurrence_overlap(self):
        _, today = self._occurrence(
            "Aujourd’hui", start=self.now + timedelta(hours=2), place=self.lubumbashi
        )
        _, tomorrow = self._occurrence(
            "Demain", start=self.now + timedelta(days=1, hours=2), place=self.lubumbashi
        )
        _, weekend = self._occurrence(
            "Samedi", start=datetime(2026, 8, 22, 11, 0, tzinfo=LUB), place=self.lubumbashi
        )
        _, crossing = self._occurrence(
            "Vendredi nuit",
            start=datetime(2026, 8, 21, 23, 30, tzinfo=LUB),
            end=datetime(2026, 8, 22, 1, 0, tzinfo=LUB),
            place=self.lubumbashi,
        )
        self.assertEqual(
            {item.occurrence_id for item in search_occurrences({"when": "today"}, now=self.now).items},
            {str(today.pk)},
        )
        tomorrow_ids = {
            item.occurrence_id for item in search_occurrences({"when": "tomorrow"}, now=self.now).items
        }
        self.assertIn(str(tomorrow.pk), tomorrow_ids)
        weekend_ids = {
            item.occurrence_id for item in search_occurrences({"when": "weekend"}, now=self.now).items
        }
        self.assertIn(str(weekend.pk), weekend_ids)
        self.assertIn(str(crossing.pk), weekend_ids)
        exact_ids = {
            item.occurrence_id
            for item in search_occurrences({"date": "2026-08-22"}, now=self.now).items
        }
        self.assertIn(str(weekend.pk), exact_ids)
        self.assertIn(str(crossing.pk), exact_ids)
        range_ids = {
            item.occurrence_id
            for item in search_occurrences(
                {"date_from": "2026-08-20", "date_to": "2026-08-21"}, now=self.now
            ).items
        }
        self.assertIn(str(today.pk), range_ids)
        self.assertIn(str(tomorrow.pk), range_ids)
        self.assertNotIn(str(weekend.pk), range_ids)

    def test_local_date_can_differ_from_utc_date(self):
        island = Place.objects.create(
            name="Kiritimati Discovery",
            locality="Kiritimati",
            country_code="KI",
            latitude=Decimal("1.872100"),
            longitude=Decimal("-157.427800"),
            timezone="Pacific/Kiritimati",
        )
        SpacePlace.objects.create(
            organization=self.space,
            place=island,
            role=SpacePlaceRole.SERVICE_POINT,
            is_public=True,
        )
        _, occurrence = self._occurrence(
            "Minuit local",
            start=datetime(2026, 8, 20, 10, 30, tzinfo=UTC),
            end=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
            place=island,
            timezone_name="Pacific/Kiritimati",
        )
        now = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
        result = search_occurrences(
            {"place": "Kiritimati", "when": "tomorrow"},
            now=now,
        )
        self.assertEqual(result.timezone_name, "Pacific/Kiritimati")
        self.assertIn(str(occurrence.pk), {item.occurrence_id for item in result.items})

    def test_text_place_nearby_and_missing_coordinates(self):
        _, near = self._occurrence(
            "Atelier Cuivre", start=self.now + timedelta(days=1), place=self.lubumbashi
        )
        no_gps = Place.objects.create(
            name="Salle sans GPS",
            locality="Lubumbashi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
        )
        _, no_gps_occ = self._occurrence(
            "Formation Locale", start=self.now + timedelta(days=1, hours=1), place=no_gps
        )
        _, far = self._occurrence(
            "Kolwezi Lointain", start=self.now + timedelta(days=1), place=self.kolwezi
        )
        self.assertIn(
            str(near.pk),
            {item.occurrence_id for item in search_occurrences({"q": "Cuivre"}, now=self.now).items},
        )
        locality = search_occurrences({"place": "Lubumbashi"}, now=self.now)
        self.assertIn(str(no_gps_occ.pk), {item.occurrence_id for item in locality.items})
        no_gps_item = next(item for item in locality.items if item.occurrence_id == str(no_gps_occ.pk))
        self.assertIsNone(no_gps_item.place.latitude)
        nearby = search_occurrences(
            {"lat": "-11.6647", "lon": "27.4794", "radius_km": "10"}, now=self.now
        )
        nearby_ids = {item.occurrence_id for item in nearby.items}
        self.assertIn(str(near.pk), nearby_ids)
        self.assertNotIn(str(far.pk), nearby_ids)
        self.assertNotIn(str(no_gps_occ.pk), nearby_ids)
        near_item = next(item for item in nearby.items if item.occurrence_id == str(near.pk))
        self.assertLess(near_item.distance_km, 0.1)

    def test_price_uses_available_offer_and_capacity_uses_pool(self):
        _, occurrence, active_paid, pool = self._event(
            "Tarifs canoniques",
            start=self.now + timedelta(days=1),
            place=self.lubumbashi,
            price="12.00",
        )
        Offer.objects.create(
            activity=occurrence.activity,
            occurrence=occurrence,
            name="Ancienne gratuité",
            unit_price=Decimal("0.00"),
            currency="USD",
            payment_mode=PaymentMode.NONE,
            status=OfferStatus.INACTIVE,
        )
        result = search_occurrences({"q": "Tarifs canoniques"}, now=self.now)
        item = result.items[0]
        self.assertFalse(item.price.is_free)
        self.assertEqual(item.price.minimum, active_paid.unit_price)
        self.assertEqual(item.availability.state, "available")

        journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=occurrence.activity,
            occurrence=occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.DRAFT,
        )
        CapacityReservation.objects.create(
            pool=pool,
            journey=journey,
            quantity=20,
            status=CapacityReservationStatus.COMMITTED,
        )
        sold_out = search_occurrences({"q": "Tarifs canoniques"}, now=self.now).items[0]
        self.assertEqual(sold_out.availability.state, "sold_out")
        self.assertEqual(sold_out.availability.label, "Complet")

        _, unlimited_occ = self._occurrence(
            "Sans limite", start=self.now + timedelta(days=2), place=self.lubumbashi
        )
        CapacityPool.objects.create(
            activity=unlimited_occ.activity,
            occurrence=unlimited_occ,
            label="Illimité",
            total_quantity=None,
        )
        unlimited = search_occurrences({"q": "Sans limite"}, now=self.now).items[0]
        self.assertEqual(unlimited.availability.state, "unlimited")

    def test_free_filter_requires_current_available_free_offer(self):
        _, free_occ, _, _ = self._event(
            "Gratuit réel",
            start=self.now + timedelta(days=1),
            place=self.lubumbashi,
            price="0.00",
        )
        _, paid_occ, _, _ = self._event(
            "Payant réel",
            start=self.now + timedelta(days=1, hours=1),
            place=self.lubumbashi,
            price="8.00",
        )
        ids = {item.occurrence_id for item in search_occurrences({"price": "free"}, now=self.now).items}
        self.assertIn(str(free_occ.pk), ids)
        self.assertNotIn(str(paid_occ.pk), ids)

    def test_private_space_place_does_not_leak_through_map_api(self):
        private_place = Place.objects.create(
            name="Bureau privé",
            locality="Lubumbashi",
            country_code="CD",
            latitude=Decimal("-11.650000"),
            longitude=Decimal("27.490000"),
            timezone="Africa/Lubumbashi",
            access_instructions="Code secret interne",
        )
        SpacePlace.objects.create(
            organization=self.space,
            place=private_place,
            role=SpacePlaceRole.OFFICE,
            is_public=False,
        )
        self._occurrence(
            "Activité lieu privé",
            start=self.now + timedelta(days=1),
            place=private_place,
        )
        response = self.client.get(reverse("discovery_api:map"), {"q": "Activité lieu privé"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        self.assertNotIn("Code secret", response.content.decode())

    def test_map_payload_is_minimal_and_private_activity_never_leaks(self):
        _, public_occ, _, _ = self._event(
            "Public API",
            start=self.now + timedelta(days=1),
            place=self.lubumbashi,
            price="5.00",
        )
        self._event(
            "Private API",
            start=self.now + timedelta(days=1),
            place=self.lubumbashi,
            visibility=ActivityVisibility.PRIVATE,
        )
        response = self.client.get(reverse("discovery_api:map"))
        self.assertEqual(response.status_code, 200)
        rows = response.json()["results"]
        row = next(item for item in rows if item["occurrence_id"] == str(public_occ.pk))
        self.assertEqual(row["vertical"], "event")
        self.assertEqual(row["place"]["latitude"], float(self.lubumbashi.latitude))
        serialized = str(row).lower()
        for forbidden in ("journey", "payment", "access", "participant", "instructions"):
            self.assertNotIn(forbidden, serialized)
        self.assertNotContains(response, "Private API")

    def test_query_limits_reject_pathological_public_search(self):
        with self.assertRaises(ValidationError):
            search_occurrences(
                {"date_from": "2026-08-20", "date_to": "2027-08-20"}, now=self.now
            )
        with self.assertRaises(ValidationError):
            search_occurrences(
                {"lat": "-11.66", "lon": "27.48", "radius_km": "500"}, now=self.now
            )
        with self.assertRaises(ValidationError):
            search_occurrences({"q": "x" * 121}, now=self.now)

    def test_home_is_public_and_event_bookmark_remains_event_scoped(self):
        event, _, _, _ = self._event(
            "Favori Event",
            start=self.now + timedelta(days=1),
            place=self.lubumbashi,
            price="0.00",
        )
        response = self.client.get(reverse("discovery:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Favori Event")
        self.client.force_login(self.participant)
        url = reverse("discovery:bookmark-toggle", kwargs={"event_id": event.pk})
        self.client.post(url)
        self.assertTrue(EventBookmark.objects.filter(user=self.participant, event=event).exists())
        self.client.post(url)
        self.assertFalse(EventBookmark.objects.filter(user=self.participant, event=event).exists())
