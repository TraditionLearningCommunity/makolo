from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

from accounts.api.views import MeAPIView, NotificationPreferencesAPIView
from conversations.api_views import ConversationListAPIView
from core.api.personal_views import PersonalOngoingAPIView
from notifications.api.views import NotificationListAPIView


class M100ShellRouteContractTests(SimpleTestCase):
    def assert_view(self, path, expected_view):
        match = resolve(path)
        self.assertIs(match.func.view_class, expected_view)

    def test_shell_support_routes_reuse_existing_owner_apis(self):
        self.assert_view("/api/v1/accounts/auth/me/", MeAPIView)
        self.assert_view(
            "/api/v1/accounts/notification-preferences/",
            NotificationPreferencesAPIView,
        )
        self.assert_view("/api/v1/notifications/", NotificationListAPIView)
        self.assert_view("/api/v1/conversations/", ConversationListAPIView)
        self.assert_view("/api/v1/me/ongoing/", PersonalOngoingAPIView)

    def test_calendar_is_a_reading_of_ongoing_not_a_parallel_domain(self):
        with self.assertRaises(Resolver404):
            resolve("/api/v1/me/calendar/")
