from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.services import can, grant_activity_role, grant_space_role, revoke_mandate
from geography.models import Place
from organizations.models import Organization

from .models import Activity, OccurrencePlaceRole
from .services import attach_occurrence_place, create_activity, create_occurrence


User = get_user_model()


class ActivityCoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="activity-owner", email="activity@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="activity-other", email="other-activity@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="Activity Space", created_by=self.user)
        self.other_space = Organization.objects.create(name="Other Space", created_by=self.user)

    def test_personal_activity_has_explicit_owner_and_activity_mandate(self):
        activity = create_activity(owner_profile=self.user, created_by=self.user, title="Mariage Makolo")
        self.assertIsNone(activity.space_id)
        self.assertEqual(activity.owner_profile_id, self.user.pk)
        self.assertEqual(activity.created_by_id, self.user.pk)
        self.assertTrue(can(self.user, PermissionCode.ACTIVITY_MANAGE, activity=activity))
        self.assertFalse(can(self.other, PermissionCode.ACTIVITY_MANAGE, activity=activity))
        self.assertFalse(Organization.objects.filter(name__icontains="Events").exists())

    def test_personal_activity_rejects_a_different_declared_owner(self):
        with self.assertRaises(ValidationError):
            create_activity(owner_profile=self.other, created_by=self.user, title="Forged owner")

    def test_new_activity_service_requires_exactly_one_logical_owner(self):
        with self.assertRaises(ValidationError):
            create_activity(created_by=self.user, title="No owner")
        with self.assertRaises(ValidationError):
            create_activity(space=self.space, owner_profile=self.user, created_by=self.user, title="Two owners")

    def test_legacy_ownerless_rows_remain_migration_compatible(self):
        legacy = Activity(created_by=self.user, title="Legacy", slug="legacy")
        Activity.objects.bulk_create([legacy])
        stored = Activity.objects.get(slug="legacy")
        self.assertIsNone(stored.space_id)
        self.assertIsNone(stored.owner_profile_id)
        self.assertEqual(stored.created_by_id, self.user.pk)

    def test_activity_mandate_can_delegate_and_be_revoked(self):
        activity = create_activity(owner_profile=self.user, created_by=self.user, title="Cérémonie")
        mandate = grant_activity_role(
            profile=self.other,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.user,
            source="task24-test",
        )
        self.assertTrue(can(self.other, PermissionCode.ACTIVITY_MANAGE, activity=activity))
        revoke_mandate(mandate=mandate, actor=self.user)
        self.assertFalse(can(self.other, PermissionCode.ACTIVITY_MANAGE, activity=activity))

    def test_slug_is_unique_in_profile_or_space_scope(self):
        first = create_activity(space=self.space, created_by=self.user, title="Makolo Fest")
        second = create_activity(space=self.space, created_by=self.user, title="Makolo Fest")
        other = create_activity(space=self.other_space, created_by=self.user, title="Makolo Fest")
        personal = create_activity(owner_profile=self.user, created_by=self.user, title="Makolo Fest")
        personal_other = create_activity(owner_profile=self.other, created_by=self.other, title="Makolo Fest")
        self.assertEqual(
            (first.slug, second.slug, other.slug, personal.slug, personal_other.slug),
            ("makolo-fest", "makolo-fest-2", "makolo-fest", "makolo-fest", "makolo-fest"),
        )

    def test_personal_activity_creation_view_and_space_forgery(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("activities:create"),
            {
                "title": "Anniversaire privé",
                "short_description": "",
                "description": "",
                "visibility": "private",
                "organization": "",
            },
        )
        self.assertRedirects(response, reverse("core:participant-home"))
        activity = Activity.objects.get(title="Anniversaire privé")
        self.assertEqual(activity.owner_profile_id, self.user.pk)
        self.assertIsNone(activity.space_id)

        forbidden = self.client.post(
            reverse("activities:create"),
            {
                "title": "Forged Space",
                "short_description": "",
                "description": "",
                "visibility": "private",
                "organization": str(self.space.pk),
            },
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertFalse(Activity.objects.filter(title="Forged Space").exists())

        grant_space_role(
            profile=self.user,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.user,
            source="task24-test",
        )
        allowed = self.client.post(
            reverse("activities:create"),
            {
                "title": "Space Activity",
                "short_description": "",
                "description": "",
                "visibility": "private",
                "organization": str(self.space.pk),
            },
        )
        self.assertRedirects(allowed, reverse("core:participant-home"))
        space_activity = Activity.objects.get(title="Space Activity")
        self.assertEqual(space_activity.space_id, self.space.pk)
        self.assertIsNone(space_activity.owner_profile_id)
        self.assertEqual(space_activity.created_by_id, self.user.pk)

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
