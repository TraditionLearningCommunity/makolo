from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase
from django.utils import timezone

from activities.models import ActivityStatus, OccurrencePlaceRole, OccurrenceStatus
from activities.services import attach_occurrence_place, reschedule_occurrence, update_activity_common
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from geography.models import Place
from organizations.models import Organization

from .activity_bridge import sync_event_core
from .models import Event, EventVenue, EventVisibility, VenueKind
from .services import cancel_event, publish_event


User = get_user_model()


class EventVerticalCompositionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="vertical-owner",
            email="vertical@example.test",
            password="StrongPass2026!",
        )
        self.space = Organization.objects.create(name="Vertical Space", created_by=self.user)
        grant_space_role(profile=self.user, space=self.space, role=SystemRoleCode.SPACE_OWNER)
        self.start = timezone.now() + timedelta(days=3)

    def make_event(self, **overrides):
        data = {
            "organizer": self.user,
            "organization": self.space,
            "title": "Vertical Event",
            "start_at": self.start,
            "end_at": self.start + timedelta(hours=2),
        }
        data.update(overrides)
        return Event.objects.create(**data)

    def test_new_event_is_activity_occurrence_composition(self):
        event = self.make_event()
        self.assertIsNotNone(event.activity_id)
        self.assertEqual(event.activity.space, self.space)
        self.assertEqual(event.activity.created_by, self.user)
        self.assertEqual(event.title, "Vertical Event")
        self.assertEqual(event.start_at, self.start)
        self.assertEqual(event.activity.occurrences.count(), 1)

        for removed_field in (
            "organization", "organizer", "title", "short_description", "description",
            "status", "visibility", "start_at", "end_at", "timezone", "capacity",
        ):
            with self.assertRaises(FieldDoesNotExist):
                Event._meta.get_field(removed_field)

    def test_activity_and_occurrence_updates_are_visible_without_resync(self):
        event = self.make_event()
        occurrence = event.primary_occurrence
        update_activity_common(
            activity=event.activity,
            title="Canonical title",
            visibility=EventVisibility.PRIVATE,
        )
        shifted = self.start + timedelta(hours=1)
        reschedule_occurrence(
            occurrence=occurrence,
            start_at=shifted,
            end_at=shifted + timedelta(hours=2),
            timezone="Africa/Lubumbashi",
        )
        event.activity.refresh_from_db()
        self.assertEqual(event.title, "Canonical title")
        self.assertEqual(event.visibility, EventVisibility.PRIVATE)
        self.assertEqual(event.start_at, shifted)
        self.assertEqual(sync_event_core(event)[0].pk, event.activity_id)

    def test_occurrence_place_is_the_public_physical_place(self):
        event = self.make_event()
        first = Place.objects.create(name="First Hall", created_by=self.user)
        second = Place.objects.create(name="Second Hall", created_by=self.user)
        occurrence = event.primary_occurrence
        attach_occurrence_place(
            occurrence=occurrence,
            place=first,
            role=OccurrencePlaceRole.PRIMARY,
            position=0,
        )
        self.assertEqual(event.primary_place, first)
        attach_occurrence_place(
            occurrence=occurrence,
            place=second,
            role=OccurrencePlaceRole.PRIMARY,
            position=0,
        )
        self.assertEqual(event.primary_place, second)

    def test_eventvenue_only_projects_canonical_place(self):
        place = Place.objects.create(name="Bridge Hall", created_by=self.user)
        venue = EventVenue.objects.create(name="Bridge Hall", kind=VenueKind.PHYSICAL, place=place)
        event = self.make_event(venue=venue)
        _, occurrence = sync_event_core(event)
        link = occurrence.place_links.get(role=OccurrencePlaceRole.PRIMARY)
        self.assertEqual(link.place, place)
        online = EventVenue.objects.create(
            name="Online",
            kind=VenueKind.ONLINE,
            online_url="https://example.test/live",
        )
        event.venue = online
        event.save(update_fields=["venue", "updated_at"])
        sync_event_core(event)
        self.assertFalse(occurrence.place_links.filter(role=OccurrencePlaceRole.PRIMARY).exists())

    def test_publish_and_cancel_are_canonical_transitions(self):
        event = self.make_event()
        occurrence = event.primary_occurrence
        publish_event(event=event, actor=self.user)
        event.activity.refresh_from_db()
        occurrence.refresh_from_db()
        self.assertEqual(event.activity.status, ActivityStatus.PUBLISHED)
        self.assertEqual(occurrence.status, OccurrenceStatus.SCHEDULED)
        self.assertEqual(event.status, ActivityStatus.PUBLISHED)

        cancel_event(event=event, actor=self.user)
        event.activity.refresh_from_db()
        occurrence.refresh_from_db()
        self.assertEqual(event.activity.status, ActivityStatus.CANCELLED)
        self.assertEqual(occurrence.status, OccurrenceStatus.CANCELLED)
        self.assertEqual(event.status, ActivityStatus.CANCELLED)
