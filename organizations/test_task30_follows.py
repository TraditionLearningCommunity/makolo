from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import ActivityStatus, ActivityVisibility
from activities.services import create_activity, update_activity_common
from notifications.models import Notification

from .models import Organization, OrganizationFollow, ProfileFollow
from .profile_follow_services import follow_profile


User = get_user_model()


class Task30FollowContractTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="task30-profile-organizer",
            email="task30-organizer@example.test",
            password="StrongPass2026!",
        )
        self.follower = User.objects.create_user(
            username="task30-follower",
            email="task30-follower@example.test",
            password="StrongPass2026!",
        )
        self.other = User.objects.create_user(
            username="task30-other",
            email="task30-other@example.test",
            password="StrongPass2026!",
        )
        self.organizer.profile.public_profile = True
        self.organizer.profile.searchable = True
        self.organizer.profile.save(update_fields=["public_profile", "searchable", "updated_at"])

    def test_profile_follow_is_explicit_private_and_not_self_follow(self):
        follow = follow_profile(user=self.follower, organizer_profile=self.organizer)
        self.assertEqual(follow.user_id, self.follower.pk)
        self.assertEqual(follow.organizer_profile_id, self.organizer.pk)
        self.assertEqual(ProfileFollow.objects.count(), 1)

        self.client.force_login(self.other)
        response = self.client.get(reverse("organizer_public:profile-following"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.organizer.username)

    def test_profile_follow_notifies_new_public_personal_activity(self):
        follow_profile(user=self.follower, organizer_profile=self.organizer)
        activity = create_activity(
            created_by=self.organizer,
            owner_profile=self.organizer,
            title="Atelier personnel T30",
            status=ActivityStatus.DRAFT,
            visibility=ActivityVisibility.PUBLIC,
        )
        with self.captureOnCommitCallbacks(execute=True):
            update_activity_common(activity=activity, status=ActivityStatus.PUBLISHED)
        notification = Notification.objects.get(recipient=self.follower)
        self.assertIn("Atelier personnel T30", notification.message)
        self.assertEqual(notification.metadata["organizer_profile_id"], str(self.organizer.pk))

    def test_space_follower_count_is_not_public(self):
        space = Organization.objects.create(
            name="T30 Space Follow",
            created_by=self.organizer,
            public_profile=True,
        )
        OrganizationFollow.objects.create(organization=space, user=self.follower)
        OrganizationFollow.objects.create(organization=space, user=self.other)
        response = self.client.get(reverse("organizer_public:detail", kwargs={"slug": space.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "2 abonnés")
        self.assertNotContains(response, "2 abonné")
