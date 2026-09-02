from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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
from geography.models import Place
from geography.value_objects import GeoPoint
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization
from spatiotemporal.context import get_journey_spatiotemporal_context
from spatiotemporal.hazards import get_action_advices, get_hazards
from spatiotemporal.mobility import get_mobility_context
from spatiotemporal.opportunities import get_last_minute_candidates
from spatiotemporal.providers import (
    NoOpTrafficProvider,
    NoOpWeatherProvider,
    ProviderRegistry,
    RoutingProvider,
)
from spatiotemporal.temporal import get_temporal_context
from spatiotemporal.types import RouteEstimate, TemporalState


User = get_user_model()


class FakeRoutingProvider(RoutingProvider):
    key = "fake"

    def estimate_route(self, *, origin, destination, departure_at):
        return RouteEstimate(
            duration=timedelta(minutes=30),
            distance_m=12_000,
            estimated_arrival_at=departure_at + timedelta(minutes=30),
            source=self.key,
            observed_at=departure_at,
            expires_at=departure_at + timedelta(minutes=5),
            confidence="test",
        )


class TimeoutRoutingProvider(RoutingProvider):
    key = "timeout"

    def estimate_route(self, *, origin, destination, departure_at):
        raise TimeoutError("provider timeout")


class M6SpatiotemporalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="m6-user", email="m6-user@example.test", password="StrongPass2026!"
        )
        self.other = User.objects.create_user(
            username="m6-other", email="m6-other@example.test", password="StrongPass2026!"
        )
        self.space = Organization.objects.create(
            name="M6 Space", created_by=self.other, public_profile=True
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.other,
            title="M6 Activity",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.place = Place.objects.create(
            name="M6 Place",
            locality="Bruxelles",
            country_code="BE",
            latitude="50.850300",
            longitude="4.351700",
            timezone="Europe/Brussels",
        )
        self.now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now + timedelta(hours=3),
            end_at=self.now + timedelta(hours=5),
            timezone="Europe/Brussels",
            status=OccurrenceStatus.SCHEDULED,
        )
        OccurrencePlace.objects.create(
            occurrence=self.occurrence,
            place=self.place,
            role=OccurrencePlaceRole.PRIMARY,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )

    @override_settings(SPATIOTEMPORAL_SOON_THRESHOLD_MINUTES=120)
    def test_temporal_context_is_timezone_aware_and_derived(self):
        upcoming = get_temporal_context(self.occurrence, now=self.now)
        self.assertEqual(upcoming.state, TemporalState.UPCOMING)
        self.assertEqual(round(upcoming.starts_in.total_seconds()), 3 * 3600)
        self.occurrence.start_at = self.now + timedelta(minutes=90)
        soon = get_temporal_context(self.occurrence, now=self.now)
        self.assertEqual(soon.state, TemporalState.SOON)
        self.occurrence.start_at = self.now - timedelta(minutes=10)
        self.occurrence.end_at = self.now + timedelta(minutes=10)
        active = get_temporal_context(self.occurrence, now=self.now)
        self.assertEqual(active.state, TemporalState.ACTIVE)
        self.occurrence.end_at = self.now - timedelta(minutes=1)
        ended = get_temporal_context(self.occurrence, now=self.now)
        self.assertEqual(ended.state, TemporalState.ENDED)
        self.occurrence.status = OccurrenceStatus.CANCELLED
        cancelled = get_temporal_context(self.occurrence, now=self.now)
        self.assertEqual(cancelled.state, TemporalState.CANCELLED)

    @override_settings(SPATIOTEMPORAL_SAFETY_BUFFER_MINUTES=10)
    def test_fake_route_produces_truthful_departure_recommendation(self):
        providers = ProviderRegistry(
            routing=FakeRoutingProvider(),
            traffic=NoOpTrafficProvider(),
            weather=NoOpWeatherProvider(),
        )
        origin = GeoPoint(50.84, 4.34)
        context = get_mobility_context(
            self.occurrence,
            origin=origin,
            target_arrival=self.occurrence.start_at,
            now=self.now,
            providers=providers,
        )
        self.assertEqual(
            context.recommended_departure,
            self.occurrence.start_at - timedelta(minutes=40),
        )
        self.assertEqual(context.route_estimate.source, "fake")

    def test_provider_timeout_degrades_without_false_eta(self):
        providers = ProviderRegistry(
            routing=TimeoutRoutingProvider(),
            traffic=NoOpTrafficProvider(),
            weather=NoOpWeatherProvider(),
        )
        context = get_mobility_context(
            self.occurrence,
            origin=GeoPoint(50.84, 4.34),
            target_arrival=self.occurrence.start_at,
            now=self.now,
            providers=providers,
        )
        self.assertIsNone(context.route_estimate)
        self.assertIsNone(context.recommended_departure)
        self.assertEqual(context.status, "routing_unavailable")

    def test_cancellation_precedes_leave_action(self):
        self.occurrence.status = OccurrenceStatus.CANCELLED
        mobility = get_mobility_context(
            self.occurrence,
            origin=None,
            target_arrival=self.occurrence.start_at,
            now=self.now,
        )
        hazards = get_hazards(
            occurrence=self.occurrence,
            journey=self.journey,
            mobility=mobility,
            now=self.now,
        )
        advices = get_action_advices(
            occurrence=self.occurrence,
            journey=self.journey,
            mobility=mobility,
            hazards=hazards,
            now=self.now,
        )
        self.assertEqual(advices[0].reason_code, "occurrence_cancelled")
        self.assertNotIn("leave_soon", {item.reason_code for item in advices})

    def test_journey_api_is_private_and_origin_is_not_persisted(self):
        other_journey = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.client.force_login(self.user)
        private_url = reverse("spatiotemporal-api:journey-context", kwargs={"journey_id": other_journey.pk})
        self.assertEqual(self.client.get(private_url).status_code, 404)
        own_url = reverse("spatiotemporal-api:journey-context", kwargs={"journey_id": self.journey.pk})
        response = self.client.get(own_url, {"lat": "50.84", "lon": "4.34"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["spatial"]["origin"]["latitude"], 50.84)
        self.user.refresh_from_db()
        self.assertFalse(hasattr(self.user, "current_latitude"))
        self.assertFalse(hasattr(self.user, "current_longitude"))

    def test_capacity_release_composes_last_minute_opportunity(self):
        activity = Activity.objects.create(
            space=self.space,
            created_by=self.other,
            title="M6 Released Capacity",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        occurrence = Occurrence.objects.create(
            activity=activity,
            start_at=self.now + timedelta(hours=2),
            end_at=self.now + timedelta(hours=3),
            timezone="Europe/Brussels",
            status=OccurrenceStatus.SCHEDULED,
        )
        OccurrencePlace.objects.create(
            occurrence=occurrence,
            place=self.place,
            role=OccurrencePlaceRole.PRIMARY,
        )
        pool = CapacityPool.objects.create(
            activity=activity,
            occurrence=occurrence,
            total_quantity=2,
            source_key="m6:test:released",
        )
        other_journey = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.other,
            activity=activity,
            occurrence=occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CANCELLED,
        )
        CapacityReservation.objects.create(
            pool=pool,
            journey=other_journey,
            quantity=1,
            status=CapacityReservationStatus.RELEASED,
            released_at=self.now,
            source_key="m6-release",
        )
        rows = get_last_minute_candidates(
            self.user,
            origin=GeoPoint(50.8504, 4.3518),
            now=self.now,
        )
        row = next(item for item in rows if item.activity.pk == activity.pk)
        self.assertIn("capacity_released", row.reasons)
        self.assertIn("nearby_now", row.reasons)
        self.assertEqual(row.available_quantity, 2)

    def test_journey_context_uses_next_step_occurrence_without_copying_it(self):
        context = get_journey_spatiotemporal_context(self.journey, now=self.now)
        self.assertEqual(context["occurrence"].pk, self.occurrence.pk)
        self.assertEqual(context["spatial"].place.pk, self.place.pk)
