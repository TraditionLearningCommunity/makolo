from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from access.models import Access, AccessStatus
from accounts.models import UserProfile
from activities.models import Activity
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .models import Organization, ProfileFollow
from .profile_follow_services import follow_profile
from .services import follow_organization


User = get_user_model()


class Task30FollowClosureTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="task30-organizer",
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
        UserProfile.objects.create(
            user=self.organizer,
            public_profile=True,
            searchable=True,
        )
        self.space = Organization.objects.create(
            name="Task 30 Space",
            created_by=self.organizer,
            public_profile=True,
        )

    def test_space_follow_count_is_not_public(self):
        follow_organization(user=self.follower, organization=self.space)
        follow_organization(user=self.other, organization=self.space)
        response = self.client.get(
            reverse("organizer_public:detail", kwargs={"slug": self.space.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "2 abonnés")
        self.assertNotContains(response, "2 abonné")

    def test_profile_follow_is_private_owned_and_cannot_self_follow(self):
        follow = follow_profile(user=self.follower, organizer_profile=self.organizer)
        self.assertTrue(
            ProfileFollow.objects.filter(
                pk=follow.pk,
                organizer_profile=self.organizer,
                user=self.follower,
            ).exists()
        )
        self.client.force_login(self.follower)
        response = self.client.get(reverse("organizer_public:profile-following"))
        self.assertContains(response, self.organizer.username)

        self.client.force_login(self.other)
        response = self.client.get(reverse("organizer_public:profile-following"))
        self.assertNotContains(response, self.organizer.username)

        with self.assertRaises(ValidationError):
            follow_profile(user=self.organizer, organizer_profile=self.organizer)

    def test_profile_follow_rejects_external_next_redirect(self):
        self.client.force_login(self.follower)
        url = reverse(
            "organizer_public:profile-follow",
            kwargs={"profile_id": self.organizer.pk},
        )
        response = self.client.post(url, {"next": "https://evil.example/steal"})
        self.assertRedirects(response, url, fetch_redirect_response=False)
        self.assertTrue(
            ProfileFollow.objects.filter(
                organizer_profile=self.organizer,
                user=self.follower,
            ).exists()
        )

    def test_profile_follow_route_hides_non_public_profiles(self):
        self.organizer.profile.public_profile = False
        self.organizer.profile.save()
        self.client.force_login(self.follower)
        response = self.client.get(
            reverse(
                "organizer_public:profile-follow",
                kwargs={"profile_id": self.organizer.pk},
            )
        )
        self.assertEqual(response.status_code, 404)


class Task30UnifiedHistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="task30-history",
            email="task30-history@example.test",
            password="StrongPass2026!",
        )
        self.journey_activity = Activity.objects.create(
            owner_profile=self.user,
            created_by=self.user,
            title="Démarche T30 terminée",
        )
        self.access_activity = Activity.objects.create(
            owner_profile=self.user,
            created_by=self.user,
            title="Accès T30 utilisé",
        )
        Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.journey_activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
        )
        Access.objects.create(
            beneficiary=self.user,
            activity=self.access_activity,
            status=AccessStatus.USED,
        )
        self.client.force_login(self.user)

    def test_terminal_items_live_on_unified_history_not_active_lists(self):
        journeys = self.client.get(reverse("core:participant-journeys"))
        accesses = self.client.get(reverse("core:participant-accesses"))
        history = self.client.get(reverse("core:participant-history"))

        self.assertEqual(journeys.status_code, 200)
        self.assertEqual(accesses.status_code, 200)
        self.assertEqual(history.status_code, 200)
        self.assertNotContains(journeys, self.journey_activity.title)
        self.assertNotContains(accesses, self.access_activity.title)
        self.assertContains(journeys, "Voir l’historique")
        self.assertContains(accesses, "Voir l’historique")
        self.assertContains(history, self.journey_activity.title)
        self.assertContains(history, self.access_activity.title)
