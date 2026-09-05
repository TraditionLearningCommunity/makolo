from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from accounts.profile_activation import build_profile_activation_summary
from topics.models import OpenToKind, ProfileInterest, ProfileOpenTo, Topic


User = get_user_model()


class ProfileActivationProjectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="amina",
            email="amina@example.com",
            password="Strong-G8-password-2026!",
            first_name="Amina",
            last_name="Makolo",
        )
        self.profile = UserProfile.objects.create(user=self.user)
        self.tech = Topic.objects.create(code="technology", label="Technologie")

    def _step(self, summary, key):
        return next(step for step in summary.steps if step.key == key)

    def test_projection_is_derived_and_percentage_is_not_persisted(self):
        summary = build_profile_activation_summary(self.user, profile=self.profile)
        self.assertGreaterEqual(summary.percentage, 0)
        self.assertLessEqual(summary.percentage, 100)
        self.assertNotIn("percentage", {field.name for field in UserProfile._meta.fields})
        self.assertFalse(self.profile.profile_completed)

    def test_interests_complete_discover_step_and_raise_progress(self):
        before = build_profile_activation_summary(self.user, profile=self.profile)
        self.assertFalse(self._step(before, "interests").complete)
        ProfileInterest.objects.create(profile=self.user, topic=self.tech)
        after = build_profile_activation_summary(self.user, profile=self.profile)
        self.assertTrue(self._step(after, "interests").complete)
        self.assertGreater(after.percentage, before.percentage)

    def test_private_choices_are_not_activation_faults(self):
        self.profile.public_profile = False
        self.profile.searchable = False
        self.profile.save(update_fields=["public_profile", "searchable"])
        summary = build_profile_activation_summary(self.user, profile=self.profile)
        self.assertFalse(self._step(summary, "public_presence").applicable)
        self.assertFalse(self._step(summary, "network").applicable)
        self.assertNotEqual(getattr(summary.next_step, "key", None), "public_presence")
        self.assertNotEqual(getattr(summary.next_step, "key", None), "network")

    def test_searchable_makes_network_applicable_and_searchable_open_to_completes_it(self):
        self.profile.searchable = True
        self.profile.save(update_fields=["searchable"])
        summary = build_profile_activation_summary(self.user, profile=self.profile)
        self.assertTrue(self._step(summary, "network").applicable)
        self.assertFalse(self._step(summary, "network").complete)
        ProfileOpenTo.objects.create(
            profile=self.user,
            kind=OpenToKind.VOLUNTEER,
            is_active=True,
            is_searchable=True,
        )
        summary = build_profile_activation_summary(self.user, profile=self.profile)
        self.assertTrue(self._step(summary, "network").complete)

    def test_private_open_to_does_not_force_searchability(self):
        ProfileOpenTo.objects.create(
            profile=self.user,
            kind=OpenToKind.MENTOR,
            is_active=True,
            is_searchable=False,
        )
        summary = build_profile_activation_summary(self.user, profile=self.profile)
        self.assertTrue(self._step(summary, "network").applicable)
        self.assertTrue(self._step(summary, "network").complete)

    def test_sensitive_data_does_not_change_activation(self):
        before = build_profile_activation_summary(self.user, profile=self.profile)
        self.user.phone = "+243999000111"
        self.user.birth_date = "1995-04-12"
        self.user.save(update_fields=["phone", "birth_date"])
        self.profile.address = "Adresse privée"
        self.profile.latitude = -11.66
        self.profile.longitude = 27.48
        self.profile.save(update_fields=["address", "latitude", "longitude"])
        after = build_profile_activation_summary(self.user, profile=self.profile)
        self.assertEqual(after.percentage, before.percentage)
        self.assertEqual(after.completed_steps, before.completed_steps)


class ProfileActivationUxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="patrick",
            email="patrick@example.com",
            password="Strong-G8-password-2026!",
            first_name="Patrick",
            last_name="Makolo",
        )
        self.profile = UserProfile.objects.create(user=self.user)
        Topic.objects.filter(is_active=True).update(is_active=False)
        self.tech = Topic.objects.create(code="technology", label="Technologie")
        Topic.objects.create(code="music", label="Musique")

    def test_owner_profile_shows_private_activation_surface(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("account:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Votre Profil Makolo est activé à")
        self.assertContains(response, "Cette progression est privée")
        self.assertContains(response, "Profil Makolo :")

    def test_public_profile_does_not_show_activation_percentage(self):
        self.profile.public_profile = True
        self.profile.save(update_fields=["public_profile"])
        viewer = User.objects.create_user(
            username="viewer",
            email="viewer@example.com",
            password="Strong-viewer-password-2026!",
        )
        UserProfile.objects.create(user=viewer)
        self.client.force_login(viewer)
        response = self.client.get(reverse("account:public-profile", kwargs={"profile_id": self.user.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Profil Makolo :")
        self.assertNotContains(response, "activé à")

    def test_discover_without_interests_shows_non_blocking_prompt(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("discovery:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rendez Discover plus pertinent")
        self.assertContains(response, "Plus tard")
        self.assertContains(response, "Technologie")

    def test_quick_capture_uses_real_profile_interest_and_hides_prompt(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("account:interest-quick-capture"),
            {"topics": [str(self.tech.pk)], "next": reverse("discovery:home")},
        )
        self.assertRedirects(response, reverse("discovery:home"))
        self.assertTrue(ProfileInterest.objects.filter(profile=self.user, topic=self.tech).exists())
        response = self.client.get(reverse("discovery:home"))
        self.assertNotContains(response, "Rendez Discover plus pertinent")

    def test_discover_with_existing_interests_does_not_show_prompt(self):
        ProfileInterest.objects.create(profile=self.user, topic=self.tech)
        self.client.force_login(self.user)
        response = self.client.get(reverse("discovery:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Rendez Discover plus pertinent")

    def test_dismiss_hides_prompt_for_current_session_only(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("account:interest-prompt-dismiss"),
            {"next": reverse("discovery:home")},
        )
        self.assertRedirects(response, reverse("discovery:home"))
        response = self.client.get(reverse("discovery:home"))
        self.assertNotContains(response, "Rendez Discover plus pertinent")
        self.assertFalse(ProfileInterest.objects.filter(profile=self.user).exists())
