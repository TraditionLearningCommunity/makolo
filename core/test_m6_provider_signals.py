from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrencePlace, OccurrencePlaceRole, OccurrenceStatus
from geography.models import Place
from geography.value_objects import GeoPoint
from organizations.models import Organization

from spatiotemporal.hazards import get_hazards
from spatiotemporal.mobility import get_mobility_context
from spatiotemporal.providers import ProviderRegistry, RoutingProvider, TrafficProvider, WeatherProvider
from spatiotemporal.types import HazardSeverity, RouteEstimate, TrafficSignal, WeatherSignal


User = get_user_model()


class CapturingRoutingProvider(RoutingProvider):
    key = "capture"

    def __init__(self, *, stale=False):
        self.stale = stale
        self.received = None

    def estimate_route(self, *, origin, destination, departure_at):
        self.received = {
            "origin": origin,
            "destination": destination,
            "departure_at": departure_at,
        }
        expires_at = departure_at - timedelta(seconds=1) if self.stale else departure_at + timedelta(minutes=5)
        return RouteEstimate(
            duration=timedelta(minutes=25),
            distance_m=9_000,
            estimated_arrival_at=departure_at + timedelta(minutes=25),
            source=self.key,
            observed_at=departure_at,
            expires_at=expires_at,
        )


class HeavyTrafficProvider(TrafficProvider):
    key = "traffic-fake"

    def traffic_context(self, *, route, observed_at):
        return TrafficSignal(
            level="heavy",
            delay=timedelta(minutes=20),
            source=self.key,
            observed_at=observed_at,
            expires_at=observed_at + timedelta(minutes=5),
        )


class WarningWeatherProvider(WeatherProvider):
    key = "weather-fake"

    def weather_context(self, *, place, at, observed_at):
        return WeatherSignal(
            kind="heavy_rain",
            severity=HazardSeverity.WARNING,
            source=self.key,
            observed_at=observed_at,
            expires_at=observed_at + timedelta(minutes=10),
            summary="Forte pluie sur la fenêtre de déplacement.",
        )


class LightWeatherProvider(WeatherProvider):
    key = "weather-light"

    def weather_context(self, *, place, at, observed_at):
        return WeatherSignal(
            kind="rain",
            severity=HazardSeverity.INFO,
            source=self.key,
            observed_at=observed_at,
            expires_at=observed_at + timedelta(minutes=10),
            summary="Pluie légère.",
        )


class NoTrafficProvider(TrafficProvider):
    key = "none"

    def traffic_context(self, *, route, observed_at):
        return None


class M6ProviderSignalTests(TestCase):
    def setUp(self):
        operator = User.objects.create_user(username="m6-provider-op", password="StrongPass2026!")
        space = Organization.objects.create(name="M6 Provider Space", created_by=operator, public_profile=True)
        activity = Activity.objects.create(
            space=space,
            created_by=operator,
            title="Provider Activity",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=activity,
            start_at=self.now + timedelta(hours=2),
            end_at=self.now + timedelta(hours=3),
            timezone="Europe/Brussels",
            status=OccurrenceStatus.SCHEDULED,
        )
        place = Place.objects.create(
            name="Provider Place",
            country_code="BE",
            latitude="50.850300",
            longitude="4.351700",
            timezone="Europe/Brussels",
        )
        OccurrencePlace.objects.create(
            occurrence=self.occurrence,
            place=place,
            role=OccurrencePlaceRole.PRIMARY,
        )
        self.origin = GeoPoint(50.84, 4.34)

    def test_stale_route_is_discarded(self):
        routing = CapturingRoutingProvider(stale=True)
        providers = ProviderRegistry(routing=routing, traffic=NoTrafficProvider(), weather=LightWeatherProvider())
        mobility = get_mobility_context(
            self.occurrence,
            origin=self.origin,
            target_arrival=self.occurrence.start_at,
            now=self.now,
            providers=providers,
        )
        self.assertIsNone(mobility.route_estimate)
        self.assertIsNone(mobility.recommended_departure)
        self.assertEqual(mobility.status, "routing_unavailable")

    def test_external_traffic_and_weather_become_hazards(self):
        providers = ProviderRegistry(
            routing=CapturingRoutingProvider(),
            traffic=HeavyTrafficProvider(),
            weather=WarningWeatherProvider(),
        )
        mobility = get_mobility_context(
            self.occurrence,
            origin=self.origin,
            target_arrival=self.occurrence.start_at,
            now=self.now,
            providers=providers,
        )
        hazards = get_hazards(occurrence=self.occurrence, mobility=mobility, now=self.now)
        self.assertEqual({hazard.kind for hazard in hazards}, {"traffic_delay", "severe_weather"})
        self.assertTrue(all(hazard.hazard_class.value == "external" for hazard in hazards))

    def test_light_rain_is_informational_and_does_not_create_hazard(self):
        providers = ProviderRegistry(
            routing=CapturingRoutingProvider(),
            traffic=NoTrafficProvider(),
            weather=LightWeatherProvider(),
        )
        mobility = get_mobility_context(
            self.occurrence,
            origin=self.origin,
            target_arrival=self.occurrence.start_at,
            now=self.now,
            providers=providers,
        )
        self.assertEqual(get_hazards(occurrence=self.occurrence, mobility=mobility, now=self.now), ())

    def test_provider_payload_is_minimized_by_contract(self):
        routing = CapturingRoutingProvider()
        providers = ProviderRegistry(routing=routing, traffic=NoTrafficProvider(), weather=LightWeatherProvider())
        get_mobility_context(
            self.occurrence,
            origin=self.origin,
            target_arrival=self.occurrence.start_at,
            now=self.now,
            providers=providers,
        )
        self.assertEqual(set(routing.received), {"origin", "destination", "departure_at"})
        self.assertIsInstance(routing.received["origin"], GeoPoint)
