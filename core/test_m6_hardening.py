from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
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
from events.models import Event
from geography.models import Place
from journeys.models import Journey, JourneyStatus, WorkflowKind
from notifications.models import Notification
from organizations.models import Organization
from services.models import ServiceDetails, ServiceKind
from transport.models import TransportMode, TransportRoute, TransportService

from spatiotemporal.context import get_journey_spatiotemporal_context
from spatiotemporal.hazards import get_action_advices, hazards_from_canonical_changes
from spatiotemporal.notifications import notify_significant_journey_hazards
from spatiotemporal.types import HazardSeverity


User = get_user_model()


class M6HardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="m6-hardening",
            email="m6-hardening@example.test",
            password="StrongPass2026!",
        )
        self.operator = User.objects.create_user(
            username="m6-operator",
            email="m6-operator@example.test",
            password="StrongPass2026!",
        )
        self.space = Organization.objects.create(
            name="M6 hardening space",
            created_by=self.operator,
            public_profile=True,
        )
        self.place = Place.objects.create(
            name="M6 canonical place",
            locality="Bruxelles",
            country_code="BE",
            latitude="50.850300",
            longitude="4.351700",
            timezone="Europe/Brussels",
        )
        self.now = timezone.now()

    def _activity_occurrence(self, title):
        activity = Activity.objects.create(
            space=self.space,
            created_by=self.operator,
            title=title,
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
        return activity, occurrence

    def _journey(self, activity, occurrence, workflow=WorkflowKind.REGISTRATION):
        return Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=activity,
            occurrence=occurrence,
            workflow=workflow,
            status=JourneyStatus.CONFIRMED,
        )

    @override_settings(SPATIOTEMPORAL_SIGNIFICANT_DELAY_MINUTES=15)
    def test_delay_and_place_change_are_ephemeral_hazards_with_actions(self):
        activity, occurrence = self._activity_occurrence("Changed occurrence")
        journey = self._journey(activity, occurrence)
        hazards = hazards_from_canonical_changes(
            [
                {
                    "kind": "occurrence_delayed",
                    "source_key": "occurrence:delay:v2",
                    "delay_minutes": 30,
                    "observed_at": self.now,
                },
                {
                    "kind": "place_changed",
                    "source_key": "occurrence:place:v3",
                    "observed_at": self.now,
                },
            ],
            occurrence=occurrence,
            journey=journey,
            now=self.now,
        )
        self.assertEqual({item.kind for item in hazards}, {"occurrence_delayed", "place_changed"})
        delayed = next(item for item in hazards if item.kind == "occurrence_delayed")
        self.assertEqual(delayed.severity, HazardSeverity.WARNING)
        advices = get_action_advices(
            occurrence=occurrence,
            journey=journey,
            hazards=hazards,
            now=self.now,
        )
        self.assertEqual(
            {item.reason_code for item in advices},
            {"occurrence_delayed", "place_changed"},
        )

    def test_significant_hazard_notification_is_idempotent(self):
        activity, occurrence = self._activity_occurrence("Cancelled occurrence")
        journey = self._journey(activity, occurrence)
        Occurrence.objects.filter(pk=occurrence.pk).update(status=OccurrenceStatus.CANCELLED)
        journey.occurrence.refresh_from_db()
        first = notify_significant_journey_hazards(journey, now=self.now)
        second = notify_significant_journey_hazards(journey, now=self.now)
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(first[0].pk, second[0].pk)
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)
        self.assertNotIn("latitude", first[0].metadata)
        self.assertNotIn("longitude", first[0].metadata)

    def test_event_service_transport_and_generic_activity_use_same_m6_projection(self):
        event_activity, event_occurrence = self._activity_occurrence("M6 Event")
        Event.objects.create(activity=event_activity)

        service_activity, service_occurrence = self._activity_occurrence("M6 Service")
        ServiceDetails.objects.create(
            activity=service_activity,
            service_kind=ServiceKind.OTHER,
        )

        route = TransportRoute.objects.create(
            space=self.space,
            code="M6-MULTI-VERTICAL",
            name="M6 multi-vertical route",
        )
        transport_activity, transport_occurrence = self._activity_occurrence("M6 Transport")
        TransportService.objects.create(
            activity=transport_activity,
            route=route,
            mode=TransportMode.ROAD,
        )

        generic_activity, generic_occurrence = self._activity_occurrence("M6 Generic")

        contexts = []
        for activity, occurrence, workflow in (
            (event_activity, event_occurrence, WorkflowKind.REGISTRATION),
            (service_activity, service_occurrence, WorkflowKind.SERVICE),
            (transport_activity, transport_occurrence, WorkflowKind.RESERVATION),
            (generic_activity, generic_occurrence, WorkflowKind.REGISTRATION),
        ):
            journey = self._journey(activity, occurrence, workflow=workflow)
            contexts.append(get_journey_spatiotemporal_context(journey, now=self.now))

        self.assertEqual([context["spatial"].place.pk for context in contexts], [self.place.pk] * 4)
        self.assertTrue(all(context["temporal"].starts_in == timedelta(hours=2) for context in contexts))
        self.assertTrue(all(context["mobility"].status == "destination_only" for context in contexts))
