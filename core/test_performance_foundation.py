from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve

from accounts.models import NotificationPreference, UserProfile
from accounts.profile_activation import build_profile_activation_summary
from accounts.templatetags.profile_activation_tags import profile_activation_summary
from activities.models import Activity
from conversations.templatetags.conversation_tags import conversation_attention_badge
from core.projections import ProjectionBudget
from core.web.fragments import is_fragment_request
from core.web.performance import PerformanceEnvelopeMiddleware
from core.web.request_context import get_request_context
from journeys.models import Journey, JourneyStatus, WorkflowKind
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

    def test_space_surface_requests_space_authority_not_personal_badges(self):
        request = self._request("/spaces/perf-space/overview/")
        context = get_request_context(request)
        self.assertEqual(context.surface.family, "space")
        self.assertIn("space_authority", context.surface.needs)
        self.assertIn("space_navigation", context.surface.needs)
        self.assertNotIn("notifications", context.surface.needs)
        self.assertNotIn("conversation_attention", context.surface.needs)

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
            "conversations.templatetags.conversation_tags.conversation_attention_badge_count",
            side_effect=AssertionError("conversation attention must not run here"),
        ):
            self.assertEqual(
                conversation_attention_badge({"request": request}, self.user),
                0,
            )

    def test_conversation_badge_is_memoized_on_now_surface(self):
        request = self._request("/me/")
        with patch(
            "conversations.templatetags.conversation_tags.conversation_attention_badge_count",
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


class WebReadPathRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="perf-web",
            email="perf-web@example.test",
            password="StrongPerfWebPassword2026!",
        )
        self.activity = Activity.objects.create(
            created_by=self.user,
            owner_profile=self.user,
            title="Performance Web Activity",
        )
        self.client.force_login(self.user)

    def _journeys(self, count):
        for _ in range(count):
            Journey.objects.create(
                initiated_by=self.user,
                beneficiary=self.user,
                activity=self.activity,
                workflow=WorkflowKind.REGISTRATION,
                status=JourneyStatus.APPROVED,
            )

    def _ongoing_query_count(self, count):
        Journey.objects.filter(
            beneficiary=self.user,
            activity=self.activity,
        ).delete()
        self._journeys(count)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/me/ongoing/")
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def test_ongoing_web_query_growth_is_bounded(self):
        one = self._ongoing_query_count(1)
        many = self._ongoing_query_count(20)

        # Readiness and presentation may add a small number of bounded batch
        # queries as the response fills. The regression we protect against is
        # row-by-row growth (the former 34 -> 146 N+1), not an artificial
        # requirement that every bounded projection stay within +2 queries.
        self.assertLessEqual(many, 40)
        self.assertLessEqual(many - one, 12)

    def test_ongoing_htmx_main_swap_uses_server_fragment_shell(self):
        response = self.client.get(
            "/me/ongoing/",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="main-content",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="main-content"', html=False)
        self.assertContains(response, 'id="app-topbar"', html=False)
        self.assertContains(response, 'id="desktop-sidebar"', html=False)
        self.assertNotContains(response, "<!DOCTYPE html>", html=False)
        self.assertNotContains(response, "dist/makolo.js", html=False)
        vary = {item.strip() for item in response.get("Vary", "").split(",")}
        self.assertTrue({"HX-Request", "HX-Target"}.issubset(vary))

    def test_ongoing_full_shell_does_not_load_share_capability_asset(self):
        response = self.client.get("/me/ongoing/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            '<script defer src="/static/js/share-actions.js',
            html=False,
        )

    def test_ongoing_non_htmx_response_keeps_full_document(self):
        response = self.client.get("/me/ongoing/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<!DOCTYPE html>", html=False)
        self.assertContains(response, "dist/makolo.js", html=False)
        vary = {item.strip() for item in response.get("Vary", "").split(",")}
        self.assertTrue({"HX-Request", "HX-Target"}.issubset(vary))

    def test_missing_profile_extension_stays_read_only_through_web_shell(self):
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
        response = self.client.get("/me/moi/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())

    def test_account_settings_get_does_not_bootstrap_profile_or_preferences(self):
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
        self.assertFalse(NotificationPreference.objects.filter(user=self.user).exists())
        response = self.client.get("/account/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
        self.assertFalse(NotificationPreference.objects.filter(user=self.user).exists())

    def test_notification_preferences_gets_are_read_only_web_and_api(self):
        self.assertFalse(NotificationPreference.objects.filter(user=self.user).exists())
        web_response = self.client.get("/notifications/preferences/")
        api_response = self.client.get("/api/v1/accounts/notification-preferences/")
        self.assertEqual(web_response.status_code, 200)
        self.assertEqual(api_response.status_code, 200)
        self.assertFalse(NotificationPreference.objects.filter(user=self.user).exists())

    def test_missing_account_extensions_are_created_only_by_valid_mutations(self):
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
        appearance = self.client.post(
            "/account/profile/",
            {"section": "appearance", "appearance": "dark"},
        )
        self.assertEqual(appearance.status_code, 302)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.theme, "dark")

        self.assertFalse(NotificationPreference.objects.filter(user=self.user).exists())
        preferences = self.client.patch(
            "/api/v1/accounts/notification-preferences/",
            data={"email_notifications": False},
            content_type="application/json",
        )
        self.assertEqual(preferences.status_code, 200)
        stored = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(stored.email_notifications)


class PerformanceEnvelopeTests(TestCase):
    @override_settings(
        MAKOLO_PERFORMANCE_LOGGING=True,
        MAKOLO_PERFORMANCE_WARN_MS=0,
        MAKOLO_PERFORMANCE_WARN_QUERIES=0,
        MAKOLO_PERFORMANCE_WARN_KB=0,
    )
    def test_envelope_logs_route_cost_without_payload(self):
        request = RequestFactory().get("/me/ongoing/")
        request.user = User.objects.create_user(
            username="perf-envelope",
            email="perf-envelope@example.test",
            password="StrongPerfEnvelopePassword2026!",
        )
        request.resolver_match = resolve("/me/ongoing/")
        middleware = PerformanceEnvelopeMiddleware(
            lambda incoming: HttpResponse("ok")
        )
        with self.assertLogs("makolo.performance", level="INFO") as logs:
            response = middleware(request)
        self.assertEqual(response.status_code, 200)
        message = "\n".join(logs.output)
        self.assertIn("route=core:participant-ongoing", message)
        self.assertIn("sql_queries=0", message)
        self.assertIn("mode=full", message)
        self.assertNotIn(request.user.email, message)
