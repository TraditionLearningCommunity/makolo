"""C8 remainder: explicit Discovery failures preserve actionable, safe categories."""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, UserProfile
from intelligence.connection_management import create_connection
from intelligence.exceptions import ProviderUnavailable
from intelligence.models import ProviderScope


@patch.dict("os.environ", {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "c8-recovery-test-only"})
class DiscoveryOwnerRecoveryTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="c8-recovery-actor", password="test",
        )
        UserProfile.objects.create(user=self.actor)
        for scope in ("discovery_research", "discovery_clarify"):
            cache.delete(f"throttle_{scope}_{self.actor.pk}")
        self.client = APIClient()
        self.client.force_authenticate(self.actor)

    def test_absent_connection_proposes_owner_configuration_not_fake_provider_outage(self):
        response = self.client.post(
            "/api/v1/discovery/research/",
            {"q": "formation scientifique"}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["status"], "unavailable")
        self.assertEqual(response.data["data"]["reason"], "connection_unavailable")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.client.force_login(self.actor)
        web = self.client.post(
            reverse("discovery:research"),
            {"q": "formation scientifique"},
        )
        self.assertEqual(web.status_code, 200)
        self.assertContains(web, "Gérer mes connexions")

    def test_quota_and_network_errors_are_not_mislabelled_key_repair(self):
        create_connection(
            actor=self.actor, scope=ProviderScope.PROFILE,
            payload={
                "provider": "tavily",
                "name": "C8 Research",
                "api_key": "SECRET-C8-DO-NOT-ECHO",
                "consent": True,
            },
        )
        for technical, expected in (
            ("rate_limited", "rate_limited"),
            ("network_unavailable", "network_unavailable"),
            ("invalid_credentials", "invalid_credentials"),
        ):
            with self.subTest(technical=technical):
                with patch(
                    "intelligence.providers.tavily_web._open_url",
                    side_effect=ProviderUnavailable(technical),
                ):
                    response = self.client.post(
                        "/api/v1/discovery/research/",
                        {"q": "formation scientifique"},
                        format="json",
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["data"]["reason"], expected)
                self.assertNotIn("SECRET-C8-DO-NOT-ECHO", str(response.data))
                with patch(
                    "intelligence.providers.tavily_web._open_url",
                    side_effect=ProviderUnavailable(technical),
                ):
                    page = self.client.post(
                        reverse("discovery:research"),
                        {"q": "formation scientifique"},
                    )
                self.assertEqual(page.status_code, 200)
                self.assertEqual(
                    "Gérer mes connexions" in page.content.decode("utf-8"),
                    technical == "invalid_credentials",
                )
