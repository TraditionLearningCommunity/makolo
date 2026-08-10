from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility


User = get_user_model()


class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dashboard-user",
            email="dashboard@example.com",
            password="Strong-dashboard-password-2026!",
            is_verified=True,
        )

        start_at = timezone.now() + timedelta(days=7)
        Event.objects.create(
            organizer=self.user,
            title="Événement public",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
            published_at=timezone.now(),
        )

    def test_public_home_is_available_without_authentication(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Les événements qui font bouger votre communauté")
        self.assertContains(response, "Événement public")
        self.assertContains(response, "Créer un compte")

    def test_authenticated_home_redirects_to_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:home"))

        self.assertRedirects(response, reverse("core:dashboard"))

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response.url)

    def test_participant_dashboard_is_personal_not_organizer_metrics(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_mode"], "participant")
        self.assertNotIn("events_count", response.context)
        self.assertNotIn("users_count", response.context)
        self.assertNotIn("verified_users_count", response.context)
        self.assertContains(response, "Espace participant")
        self.assertContains(response, "Mes prochains événements")
        self.assertNotContains(response, "Paiements réussis")
        self.assertNotContains(response, "CRM & audiences")
