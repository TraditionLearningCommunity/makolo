from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import PermissionGroup, Role


User = get_user_model()


class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dashboard-user",
            email="dashboard@example.com",
            password="Strong-dashboard-password-2026!",
            is_verified=True,
        )
        Role.objects.create(
            name="Organizer",
            code="organizer",
            is_active=True,
        )
        PermissionGroup.objects.create(
            name="Event management",
            code="event-management",
        )

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response.url)

    def test_authenticated_dashboard_uses_database_metrics(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["users_count"], 1)
        self.assertEqual(response.context["verified_users_count"], 1)
        self.assertEqual(response.context["roles_count"], 1)
        self.assertEqual(response.context["permission_groups_count"], 1)
        self.assertContains(response, "Aucune donnée fictive")
