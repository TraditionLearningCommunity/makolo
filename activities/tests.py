from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from geography.models import Place
from organizations.models import Organization

from .models import Activity, OccurrencePlaceRole
from .services import attach_occurrence_place, create_activity, create_occurrence


User = get_user_model()


class ActivityCoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="activity-owner", email="activity@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="Activity Space", created_by=self.user)
        self.other_space = Organization.objects.create(name="Other Space", created_by=self.user)

    def test_new_activity_requires_space_but_legacy_model_allows_null(self):
        with self.assertRaises(ValidationError):
            create_activity(space=None, created_by=self.user, title="No space")
        self.assertIsNone(Activity.objects.create(created_by=self.user, title="Legacy").space_id)

    def test_slug_is_unique_per_space(self):
        first = create_activity(space=self.space, created_by=self.user, title="Makolo Fest")
        second = create_activity(space=self.space, created_by=self.user, title="Makolo Fest")
        other = create_activity(space=self.other_space, created_by=self.user, title="Makolo Fest")
        self.assertEqual((first.slug, second.slug, other.slug), ("makolo-fest", "makolo-fest-2", "makolo-fest"))

    def test_occurrence_validates_end_and_timezone(self):
        activity = create_activity(space=self.space, created_by=self.user, title="Session")
        start = timezone.now() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            create_occurrence(activity=activity, start_at=start, end_at=start, timezone="Africa/Lubumbashi")
        with self.assertRaises(ValidationError):
            create_occurrence(activity=activity, start_at=start, timezone="Mars/Olympus_Mons")
        first = create_occurrence(activity=activity, start_at=start + timedelta(days=1), timezone="Africa/Lubumbashi")
        second = create_occurrence(activity=activity, start_at=start, timezone="Africa/Lubumbashi")
        self.assertEqual(list(activity.occurrences.values_list("pk", flat=True)), [second.pk, first.pk])

    def test_primary_place_is_explicit_and_replaceable(self):
        activity = create_activity(space=self.space, created_by=self.user, title="Concert")
        occurrence = create_occurrence(activity=activity, start_at=timezone.now() + timedelta(days=1), timezone="Africa/Lubumbashi")
        first = Place.objects.create(name="Salle A", created_by=self.user)
        second = Place.objects.create(name="Salle B", created_by=self.user)
        link = attach_occurrence_place(occurrence=occurrence, place=first, role=OccurrencePlaceRole.PRIMARY)
        moved = attach_occurrence_place(occurrence=occurrence, place=second, role=OccurrencePlaceRole.PRIMARY)
        self.assertEqual(link.pk, moved.pk)
        self.assertEqual(moved.place, second)
        self.assertNotIn("origin", OccurrencePlaceRole.values)
        self.assertNotIn("destination", OccurrencePlaceRole.values)
