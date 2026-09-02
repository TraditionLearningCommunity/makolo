from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from geography.models import Place
from geography.value_objects import GeoPoint
from organizations.models import Organization

from spatiotemporal.mobility import get_mobility_context
from spatiotemporal.providers import NoOpTrafficProvider, NoOpWeatherProvider, ProviderRegistry, RoutingProvider
from spatiotemporal.spatial import get_spatial_context
from spatiotemporal.types import RouteEstimate


User = get_user_model()


class StaleRoutingProvider(RoutingProvider):
    key = "stale-test"

    def estimate_route(self, *, origin, destination, departure_at):
        return RouteEstimate(
            duration=timedelta(minutes=25),
            distance_m=8_000,
            estimated_arrival_at=departure_at + timedelta(minutes=25),
            source=self.key,
            observed_at=departure_at - timedelta(minutes=20),
            expires_at=departure_at - timedelta(minutes=1),
            confidence="expired-test",
        )


class M6ProviderContractTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="m6-provider-owner",
            email="m6-provider-owner@example.test",
            password="StrongPass2026!",
        )
        self.space = Organization.objects.create(
            name="M6 provider space",
            created_by=self.owner,
            public_profile=True,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="M6 provider activity",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.now = timezone.now()

    def test_stale_route_is_discarded_without_false_departure(self):
        place = Place.objects.create(
            name="M6 provider place",
            locality="Bruxelles",
            country_code="BE",
            latitude="50.850300",
            longitude="4.351700",
            timezone="Europe/Brussels",
        )
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now + timedelta(hours=2),
            end_at=self.now + timedelta(hours=3),
            timezone="Europe/Brussels",
            status=OccurrenceStatus.SCHEDULED,
        )
        occurrence.place_links.create(place=place, role="primary")
        providers = ProviderRegistry(
            routing=StaleRoutingProvider(),
            traffic=NoOpTrafficProvider(),
            weather=NoOpWeatherProvider(),
        )

        context = get_mobility_context(
            occurrence,
            origin=GeoPoint(50.84, 4.34),
            target_arrival=occurrence.start_at,
            now=self.now,
            providers=providers,
        )

        self.assertIsNone(context.route_estimate)
        self.assertIsNone(context.recommended_departure)
        self.assertEqual(context.status, "routing_unavailable")

    def test_occurrence_without_place_has_truthful_fallback(self):
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now + timedelta(hours=2),
            end_at=self.now + timedelta(hours=3),
            timezone="UTC",
            status=OccurrenceStatus.SCHEDULED,
        )

        spatial = get_spatial_context(occurrence, origin=GeoPoint(50.84, 4.34))
        mobility = get_mobility_context(
            occurrence,
            origin=GeoPoint(50.84, 4.34),
            target_arrival=occurrence.start_at,
            now=self.now,
        )

        self.assertIsNone(spatial.place)
        self.assertIsNone(spatial.destination)
        self.assertEqual(spatial.itinerary_url, "")
        self.assertEqual(mobility.status, "no_destination")
        self.assertIsNone(mobility.recommended_departure)
