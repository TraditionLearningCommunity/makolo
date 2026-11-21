from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from activities.models import Activity
from discovery.api.composition import _public_owner_facts

from .models import Organization, OrganizationFollow, ProfileFollow


User = get_user_model()


class DirectFollowAPITests(TestCase):
    def setUp(self):
        self.publisher = User.objects.create_user(
            username="direct-follow-publisher",
            email="direct-follow-publisher@example.test",
            password="follow-test-only",
        )
        self.viewer = User.objects.create_user(
            username="direct-follow-viewer",
            email="direct-follow-viewer@example.test",
            password="follow-test-only",
        )
        UserProfile.objects.create(
            user=self.publisher, public_profile=True, searchable=True,
        )
        self.space = Organization.objects.create(
            name="Direct Follow Space",
            created_by=self.publisher,
            public_profile=True,
            searchable=True,
        )
        self.profile_url = reverse(
            "organizations_api:follow-target",
            kwargs={"kind": "profile", "target_id": self.publisher.pk},
        )
        self.space_url = reverse(
            "organizations_api:follow-target",
            kwargs={"kind": "space", "target_id": self.space.pk},
        )

    def test_login_is_required_and_followers_are_not_public(self):
        for url in (self.profile_url, self.space_url):
            for method in (self.client.get, self.client.post, self.client.delete):
                self.assertIn(method(url).status_code, (401, 403))
        self.assertFalse(ProfileFollow.objects.exists())
        self.assertFalse(OrganizationFollow.objects.exists())

    def test_profile_follow_toggle_and_self_follow_rejection(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.profile_url).json(), {"followed": False})
        self.assertEqual(self.client.post(self.profile_url).json(), {"followed": True})
        self.assertEqual(self.client.post(self.profile_url).json(), {"followed": True})
        self.assertEqual(ProfileFollow.objects.count(), 1)
        self.assertEqual(self.client.delete(self.profile_url).json(), {"followed": False})
        self.assertEqual(self.client.delete(self.profile_url).json(), {"followed": False})
        self.assertFalse(ProfileFollow.objects.exists())

        self.client.force_login(self.publisher)
        self.assertEqual(self.client.post(self.profile_url).status_code, 404)
        self.publisher.profile.public_profile = False
        self.publisher.profile.save(update_fields=["public_profile"])
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(self.profile_url).status_code, 404)

    def test_space_follow_toggle_preserves_existing_preferences(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.space_url).json(), {"followed": False})
        self.assertEqual(self.client.post(self.space_url).json(), {"followed": True})
        follow = OrganizationFollow.objects.get(user=self.viewer, organization=self.space)
        follow.email_new_events = True
        follow.save(update_fields=["email_new_events"])
        self.assertEqual(self.client.post(self.space_url).json(), {"followed": True})
        follow.refresh_from_db()
        self.assertTrue(follow.email_new_events)
        self.assertEqual(self.client.delete(self.space_url).json(), {"followed": False})
        self.assertFalse(OrganizationFollow.objects.exists())

        self.space.searchable = False
        self.space.save(update_fields=["searchable"])
        self.assertEqual(self.client.post(self.space_url).status_code, 404)

    def test_discovery_projects_only_the_viewers_follow_state(self):
        profile_activity = Activity.objects.create(
            created_by=self.publisher,
            owner_profile=self.publisher,
            title="Public personal presentation",
        )
        space_activity = Activity.objects.create(
            created_by=self.publisher,
            space=self.space,
            title="Public space presentation",
        )
        activity_ids = [profile_activity.pk, space_activity.pk]
        anonymous, _ = _public_owner_facts(activity_ids, [])
        self.assertNotIn("follow", anonymous[str(profile_activity.pk)]["owner"])
        self.assertNotIn("follow", anonymous[str(space_activity.pk)]["owner"])

        before, _ = _public_owner_facts(activity_ids, [], profile=self.viewer)
        self.assertEqual(
            before[str(profile_activity.pk)]["owner"]["follow"],
            {"followed": False, "can_toggle": True},
        )
        self.assertEqual(
            before[str(space_activity.pk)]["owner"]["follow"],
            {"followed": False, "can_toggle": True},
        )
        ProfileFollow.objects.create(user=self.viewer, organizer_profile=self.publisher)
        OrganizationFollow.objects.create(user=self.viewer, organization=self.space)
        after, _ = _public_owner_facts(activity_ids, [], profile=self.viewer)
        self.assertTrue(after[str(profile_activity.pk)]["owner"]["follow"]["followed"])
        self.assertTrue(after[str(space_activity.pk)]["owner"]["follow"]["followed"])
        own, _ = _public_owner_facts([profile_activity.pk], [], profile=self.publisher)
        self.assertNotIn("follow", own[str(profile_activity.pk)]["owner"])
