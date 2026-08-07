from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PermissionGroup, Role
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
        Role.objects.create(
            name="Organizer",
            code="organizer",
            is_active=True,
        )
        PermissionGroup.objects.create(
            name="Event management",
            code="event-management",
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
        self.assertEqual(response.context["events_count"], 1)
        self.assertEqual(response.context["published_events_count"], 1)
        self.assertEqual(response.context["upcoming_events_count"], 1)
        self.assertContains(response, "Prochains événements")
        self.assertContains(response, "Événement public")
