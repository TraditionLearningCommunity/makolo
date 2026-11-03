"""C8 operational observations: useful statuses, never search text or keys."""
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User, UserProfile


class C8SafeExternalActionLoggingTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="c8-telemetry", password="test",
        )
        UserProfile.objects.create(user=self.actor)
        self.client = APIClient()
        self.client.force_authenticate(self.actor)

    def test_no_provider_research_is_diagnostic_without_query_leak(self):
        private_query = "C8-PRIVATE-QUERY-NOT-TO-LOG"
        with self.assertLogs("makolo.discovery", level="INFO") as events:
            result = self.client.post(
                "/api/v1/discovery/research/",
                {"q": private_query}, format="json",
            )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["data"]["status"], "unavailable")
        self.assertEqual(len(events.records), 1)
        row = events.records[0]
        self.assertEqual(row.makolo_event, "discovery.external_action")
        self.assertEqual(row.action, "research")
        self.assertEqual(row.status, "unavailable")
        self.assertEqual(row.reason, "connection_unavailable")
        self.assertNotIn(private_query, str(row.__dict__))
        self.assertNotIn("api_key", str(row.__dict__))
        self.assertNotIn("provider_token", str(row.__dict__))

    def test_clarification_status_has_no_raw_user_intent(self):
        private_query = "quelque chose de calme avec mes amis C8-SECRET-TEXT"
        with self.assertLogs("makolo.discovery", level="INFO") as events:
            result = self.client.post(
                "/api/v1/discovery/clarify/",
                {"criteria": {"q": private_query}}, format="json",
            )
        self.assertEqual(result.status_code, 200)
        self.assertIn(
            result.data["data"]["status"],
            {"unavailable", "already_structured", "unchanged"},
        )
        self.assertEqual(events.records[0].action, "clarify")
        self.assertNotIn(private_query, str(events.records[0].__dict__))
