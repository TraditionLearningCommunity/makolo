from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import resolve

from accounts.models import UserProfile
from accounts.profile_activation import build_profile_activation_summary
from accounts.templatetags.profile_activation_tags import profile_activation_summary
from conversations.templatetags.conversation_tags import conversation_attention_badge
from core.projections import ProjectionBudget
from core.web.fragments import is_fragment_request
from core.web.request_context import get_request_context
from notifications.context_processors import notifications_summary


User = get_user_model()


class ProjectionBudgetTests(TestCase):
    def test_budget_takes_only_remaining_items_without_reordering(self):
        budget = ProjectionBudget(limit=3)
        self.assertEqual(budget.take([3, 1]), [3, 1])
        self.assertEqual(budget.remaining, 1)
        self.assertEqual(budget.take([7, 8, 9]), [7])
        self.assertTrue(budget.full)


class RequestPerformanceFoundationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="perf-foundation",
            email="perf-foundation@example.test",
            password="StrongPerfPassword2026!",
        )

    def _request(self, path, **extra):
        request = self.factory.get(path, **extra)
        request.user = self.user
        request.resolver_match = resolve(path)
        return request

    def test_request_context_is_small_lazy_and_stable_for_request(self):
        request = self._request("/me/ongoing/")
        context = get_request_context(request)
        self.assertIs(context, get_request_context(request))
        self.assertEqual(context.surface.family, "personal")
        self.assertEqual(context.surface.owner, "ongoing")
        self.assertNotIn("notifications", context.surface.needs)
        self.assertNotIn("conversation_attention", context.surface.needs)
        self.assertFalse(hasattr(context, "journeys"))
        self.assertFalse(hasattr(context, "permissions"))

    def test_fragment_helper_uses_explicit_htmx_headers(self):
        request = self._request(
            "/me/ongoing/",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="main-content",
        )
        self.assertTrue(is_fragment_request(request))
        self.assertTrue(is_fragment_request(request, target="main-content"))
        self.assertFalse(is_fragment_request(request, target="app-topbar"))

    def test_notifications_are_not_queried_off_now_surface(self):
        request = self._request("/me/ongoing/")
        with patch(
            "notifications.context_processors.get_unread_notifications_count",
            side_effect=AssertionError("notification count must not run here"),
        ):
            self.assertEqual(
                notifications_summary(request),
                {"notifications_unread_count": 0},
            )

    def test_notification_count_is_memoized_on_now_surface(self):
        request = self._request("/me/")
        with patch(
            "notifications.context_processors.get_unread_notifications_count",
            return_value=4,
        ) as counter:
            self.assertEqual(notifications_summary(request)["notifications_unread_count"], 4)
            self.assertEqual(notifications_summary(request)["notifications_unread_count"], 4)
        counter.assert_called_once_with(self.user)

    def test_profile_activation_does_not_create_profile_on_read(self):
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
        summary = build_profile_activation_summary(self.user)
        self.assertGreaterEqual(summary.available_steps, 1)
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())

    def test_profile_activation_template_projection_is_request_memoized(self):
        UserProfile.objects.create(user=self.user)
        request = self._request("/me/ongoing/")
        with patch(
            "accounts.templatetags.profile_activation_tags.build_profile_activation_summary",
            wraps=build_profile_activation_summary,
        ) as builder:
            first = profile_activation_summary({"request": request})
            second = profile_activation_summary({"request": request})
        self.assertEqual(first, second)
        builder.assert_called_once_with(self.user)

    def test_conversation_badge_is_not_computed_off_now_surface(self):
        request = self._request("/me/ongoing/")
        with patch(
            "conversations.templatetags.conversation_tags.conversation_attention_count",
            side_effect=AssertionError("conversation attention must not run here"),
        ):
            self.assertEqual(
                conversation_attention_badge({"request": request}, self.user),
                0,
            )

    def test_conversation_badge_is_memoized_on_now_surface(self):
        request = self._request("/me/")
        with patch(
            "conversations.templatetags.conversation_tags.conversation_attention_count",
            return_value=2,
        ) as counter:
            self.assertEqual(
                conversation_attention_badge({"request": request}, self.user),
                2,
            )
            self.assertEqual(
                conversation_attention_badge({"request": request}, self.user),
                2,
            )
        counter.assert_called_once()
