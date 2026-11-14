"""C8 complete owner journey: connect -> use -> rotate/disable -> revoke.

Provider HTTP is mocked. A real provider and billable request are NOT assumed.
"""
import json
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User, UserProfile
from intelligence.models import ProviderConnection, ProviderCredential


class _ProviderReply:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({
            "results": [{
                "title": "Public opportunity reference",
                "url": "https://example.org/reference",
                "content": "Public information requiring verification.",
            }],
        }).encode("utf-8")


@patch.dict(
    "os.environ",
    {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "c8-e2e-only-master-key"},
)
class C8OwnerInteropJourneyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="c8-real-journey", password="test",
        )
        UserProfile.objects.create(user=self.owner)
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.root = "/api/v1/me/intelligence/connections/"
        self.research = "/api/v1/discovery/research/"

    def _research_with(self, *, key):
        with patch(
            "intelligence.providers.tavily_web._open_url",
            return_value=_ProviderReply(),
        ) as outbound:
            result = self.api.post(
                self.research, {"q": "bourse de recherche"}, format="json",
            )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result["Cache-Control"], "private, no-store")
        self.assertEqual(result.data["data"]["status"], "completed")
        self.assertEqual(
            result.data["data"]["candidates"][0]["sources"][0]["url"],
            "https://example.org/reference",
        )
        sent = outbound.call_args.args[0]
        self.assertEqual(sent.get_header("Authorization"), f"Bearer {key}")
        self.assertNotIn(key, str(result.data))

    def test_lifecycle_and_real_discovery_consumption_share_one_owner(self):
        created = self.api.post(self.root, {
            "provider": "tavily",
            "name": "Mon exploration",
            "api_key": "C8-TEST-KEY-ORIGINAL",
            "consent": True,
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        identity = created.data["id"]
        detail = self.root + identity + "/"
        self.assertNotIn("C8-TEST-KEY-ORIGINAL", str(created.data))
        self.assertIn(identity, [
            row["id"] for row in
            self.api.get("/api/v1/me/interoperability/").data["connections"]
        ])
        self._research_with(key="C8-TEST-KEY-ORIGINAL")

        disabled = self.api.patch(
            detail, {"enabled": False}, format="json",
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.data["usable"])
        with patch("intelligence.providers.tavily_web._open_url") as network:
            unavailable = self.api.post(
                self.research, {"q": "bourse de recherche"}, format="json",
            )
        self.assertEqual(unavailable.status_code, 200)
        self.assertEqual(unavailable.data["data"]["status"], "unavailable")
        network.assert_not_called()

        enabled = self.api.patch(detail, {"enabled": True}, format="json")
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(enabled.data["health"], "unknown")
        rotated = self.api.patch(
            detail, {"api_key": "C8-TEST-KEY-ROTATED"}, format="json",
        )
        self.assertEqual(rotated.status_code, 200)
        self.assertNotIn("C8-TEST-KEY-ROTATED", str(rotated.data))
        self._research_with(key="C8-TEST-KEY-ROTATED")

        removed = self.api.delete(detail)
        self.assertEqual(removed.status_code, 204)
        self.assertFalse(
            ProviderConnection.objects.filter(pk=identity).exists()
        )
        self.assertFalse(
            ProviderCredential.objects.filter(connection_id=identity).exists()
        )
        with patch("intelligence.providers.tavily_web._open_url") as network:
            after = self.api.post(
                self.research, {"q": "bourse de recherche"}, format="json",
            )
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.data["data"]["status"], "unavailable")
        network.assert_not_called()
        self.assertNotIn(identity, [
            row["id"] for row in
            self.api.get("/api/v1/me/interoperability/").data["connections"]
        ])
