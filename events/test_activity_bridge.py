import importlib
from datetime import timedelta

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import ActivityStatus, OccurrencePlaceRole, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from geography.models import Place
from organizations.models import Organization

from .activity_bridge import sync_event_core
from .models import Event, EventStatus, EventVenue, EventVisibility, VenueKind
from .services import cancel_event, publish_event


User = get_user_model()


class EventActivityBridgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bridge-owner", email="bridge@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="Bridge Space", created_by=self.user)
        grant_space_role(profile=self.user, space=self.space, role=SystemRoleCode.SPACE_OWNER)
        self.start = timezone.now() + timedelta(days=3)

    def make_event(self, **overrides):
        data = {"organizer": self.user, "organization": self.space, "title": "Bridge Event", "start_at": self.start, "end_at": self.start + timedelta(hours=2)}
        data.update(overrides)
        return Event.objects.create(**data)

    def test_bridge_creates_and_updates_single_activity_occurrence(self):
        event = self.make_event()
        activity, occurrence = sync_event_core(event)
        event.refresh_from_db()
        self.assertEqual(event.activity_id, activity.pk)
        self.assertEqual(activity.occurrences.count(), 1)
        event.title = "Bridge Event Updated"
        event.start_at += timedelta(hours=1)
        event.end_at += timedelta(hours=1)
        event.visibility = EventVisibility.PRIVATE
        event.save()
        activity2, occurrence2 = sync_event_core(event)
        self.assertEqual(activity.pk, activity2.pk)
        self.assertEqual(occurrence.pk, occurrence2.pk)
        activity2.refresh_from_db(); occurrence2.refresh_from_db()
        self.assertEqual(activity2.title, event.title)
        self.assertEqual(activity2.visibility, EventVisibility.PRIVATE)
        self.assertEqual(occurrence2.start_at, event.start_at)

    def test_physical_place_projects_but_online_requires_no_place(self):
        place = Place.objects.create(name="Bridge Hall", created_by=self.user)
        venue = EventVenue.objects.create(name="Bridge Hall", kind=VenueKind.PHYSICAL, place=place)
        event = self.make_event(venue=venue)
        _, occurrence = sync_event_core(event)
        link = occurrence.place_links.get(role=OccurrencePlaceRole.PRIMARY)
        self.assertEqual(link.place, place)
        online = EventVenue.objects.create(name="Online", kind=VenueKind.ONLINE, online_url="https://example.test/live")
        event.venue = online; event.save(update_fields=["venue", "updated_at"])
        sync_event_core(event)
        self.assertFalse(occurrence.place_links.filter(role=OccurrencePlaceRole.PRIMARY).exists())
        self.assertEqual(online.online_url, "https://example.test/live")

    def test_publish_and_cancel_keep_core_statuses_coherent(self):
        event = self.make_event()
        sync_event_core(event)
        publish_event(event=event, actor=self.user)
        event.activity.refresh_from_db()
        occurrence = event.activity.occurrences.get()
        self.assertEqual(event.activity.status, ActivityStatus.PUBLISHED)
        self.assertEqual(occurrence.status, OccurrenceStatus.SCHEDULED)
        cancel_event(event=event, actor=self.user)
        event.activity.refresh_from_db(); occurrence.refresh_from_db()
        self.assertEqual(event.activity.status, ActivityStatus.CANCELLED)
        self.assertEqual(occurrence.status, OccurrenceStatus.CANCELLED)


class EventActivityBackfillTests(TestCase):
    def test_backfill_is_one_to_one_handles_legacy_and_does_not_merge_same_titles(self):
        user = User.objects.create_user(username="legacy-event", email="legacy-event@example.test", password="StrongPass2026!")
        start = timezone.now() + timedelta(days=5)
        first = Event.objects.create(organizer=user, title="Same title", start_at=start, end_at=start+timedelta(hours=1), status=EventStatus.PUBLISHED, visibility=EventVisibility.UNLISTED)
        second = Event.objects.create(organizer=user, title="Same title", start_at=start+timedelta(days=1), end_at=start+timedelta(days=1, hours=1))
        migration = importlib.import_module("events.migrations.0005_backfill_activity_occurrence")
        migration.backfill_event_core(apps, None)
        first.refresh_from_db(); second.refresh_from_db()
        self.assertIsNotNone(first.activity_id)
        self.assertIsNotNone(second.activity_id)
        self.assertNotEqual(first.activity_id, second.activity_id)
        self.assertIsNone(first.activity.space_id)
        self.assertEqual(first.activity.visibility, EventVisibility.UNLISTED)
        self.assertEqual(first.activity.occurrences.get().status, OccurrenceStatus.SCHEDULED)
