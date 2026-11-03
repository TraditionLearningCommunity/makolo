"""C5: user-invoked Discovery actions consume the C4 scoped Intelligence channels."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import UserProfile
from intelligence.connection_management import create_connection
from intelligence.models import ProviderScope


class _Reply:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.value).encode("utf-8")


@patch.dict("os.environ", {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "test-only-c5-key"})
class DiscoveryConnectedActionsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.actor = User.objects.create_user(
            username="c5-actor", password="test-password",
        )
        self.other = User.objects.create_user(
            username="c5-other", password="test-password",
        )
        self.profile = UserProfile.objects.create(user=self.actor)
        for user in (self.actor, self.other):
            for scope in ("discovery_clarify", "discovery_research"):
                cache.delete(f"throttle_{scope}_{user.pk}")
        self.api = APIClient()
        self.api.force_authenticate(self.actor)

    def _connect(self, provider, *, model=""):
        return create_connection(
            actor=self.actor, scope=ProviderScope.PROFILE,
            payload={
                "provider": provider, "name": f"C5 {provider}",
                "api_key": f"TEST-C5-KEY-{provider}",
                "model": model, "consent": True,
            },
        )

    def test_clarify_requires_owner_and_valid_payload(self):
        self.api.force_authenticate(user=None)
        response = self.api.post("/api/v1/discovery/clarify/", {
            "criteria": {"q": "quelque chose de calme"},
        }, format="json")
        self.assertIn(response.status_code, {401, 403})
        self.api.force_authenticate(self.actor)
        for invalid in (
            {"criteria": {"q": "test", "profile_id": str(self.other.pk)}},
            {"criteria": {"q": "x" * 121}},
            {"criteria": "pas une recherche"},
        ):
            response = self.api.post(
                "/api/v1/discovery/clarify/", invalid, format="json",
            )
            self.assertEqual(response.status_code, 400, response.data)

    def test_clarify_uses_only_own_openai_route_and_canonicalizes_output(self):
        self._connect("openai", model="test-model")
        other_client = APIClient()
        other_client.force_authenticate(self.other)
        unrelated = other_client.post("/api/v1/discovery/clarify/", {
            "criteria": {"q": "quelque chose de calme avec mes amis"},
        }, format="json")
        self.assertEqual(unrelated.status_code, 200)
        self.assertEqual(unrelated.data["data"]["status"], "unavailable")

        with patch("intelligence.providers.openai_compatible._open_url",
                   return_value=_Reply({
                       "choices": [{
                           "message": {"content": json.dumps({
                               "vertical": "event", "place": "",
                               "when": "tomorrow", "period": "evening",
                               "price": "", "text": "calme",
                           })},
                       }],
                   })) as outbound:
            response = self.api.post("/api/v1/discovery/clarify/", {
                "criteria": {"q": "quelque chose de calme avec mes amis"},
            }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["meta"]["projection"], "discovery.clarification")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response.data["data"]["status"], "applied")
        self.assertEqual(response.data["data"]["query"]["vertical"], "event")
        self.assertEqual(response.data["data"]["query"]["when"], "tomorrow")
        self.assertTrue(outbound.called)
        serialized = str(response.data)
        self.assertNotIn("TEST-C5-KEY", serialized)
        self.assertNotIn("provider_key", serialized)
        self.assertFalse(
            any(row["source"] == "default"
                for row in response.data["data"]["constraints"])
        )

    def test_explicit_filters_never_trigger_paid_provider(self):
        self._connect("openai", model="test-model")
        with patch("intelligence.providers.openai_compatible._open_url") as network:
            response = self.api.post("/api/v1/discovery/clarify/", {
                "criteria": {"q": "gospel", "vertical": "event"},
            }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["status"], "already_structured")
        self.assertEqual(response.data["data"]["query"]["vertical"], "event")
        network.assert_not_called()

    def test_normal_discovery_get_never_triggers_external_provider(self):
        self._connect("openai", model="test-model")
        with patch("intelligence.providers.openai_compatible._open_url") as network:
            response = self.api.get(
                "/api/v1/discovery/items/",
                {"q": "quelque chose de calme avec mes amis"},
            )
        self.assertEqual(response.status_code, 200)
        network.assert_not_called()

    def test_web_research_keeps_only_https_source_backed_pointers(self):
        self._connect("tavily")
        with patch("intelligence.providers.tavily_web._open_url",
                   return_value=_Reply({"results": [
                       {
                           "title": "Document public",
                           "url": "https://example.org/public",
                           "content": "Une piste publique à vérifier.",
                       },
                       {
                           "title": "Local",
                           "url": "https://127.0.0.1/internal",
                           "content": "A rejeter.",
                       },
                   ]})):
            response = self.api.post(
                "/api/v1/discovery/research/",
                {"q": "bourse en ingénierie"}, format="json",
            )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response.data["meta"]["projection"], "discovery.source-leads")
        self.assertEqual(len(response.data["data"]["candidates"]), 1)
        lead = response.data["data"]["candidates"][0]
        self.assertEqual(lead["sources"][0]["url"], "https://example.org/public")
        self.assertNotIn("TEST-C5-KEY", str(response.data))
        self.assertNotIn("127.0.0.1", str(response.data))

    def test_web_research_non_owner_cannot_use_personal_key(self):
        self._connect("exa")
        self.api.force_authenticate(self.other)
        with patch("intelligence.providers.exa_web._open_url") as network:
            result = self.api.post(
                "/api/v1/discovery/research/",
                {"q": "formation informatique"}, format="json",
            )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["data"]["status"], "unavailable")
        network.assert_not_called()

    def test_external_provider_failure_exposes_only_safe_reason(self):
        from intelligence.exceptions import ProviderUnavailable

        self._connect("tavily")
        for technical, public in (
            ("invalid_credentials", "invalid_credentials"),
            ("rate_limited", "rate_limited"),
            ("network_unavailable", "network_unavailable"),
        ):
            with self.subTest(technical=technical):
                with patch(
                    "intelligence.providers.tavily_web._open_url",
                    side_effect=ProviderUnavailable(technical),
                ):
                    response = self.api.post("/api/v1/discovery/research/", {
                        "q": "formation professionnelle",
                    }, format="json")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["data"]["status"], "unavailable")
                self.assertEqual(response.data["data"]["reason"], public)
                self.assertNotIn("TEST-C5-KEY", str(response.data))

    def test_source_research_web_requires_csrf(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        response = client.post(reverse("discovery:research"), {
            "q": "formation informatique",
        })
        self.assertEqual(response.status_code, 403)

    def test_web_clarification_preserves_location_context(self):
        self.client.force_login(self.actor)
        url = reverse("discovery:clarify")
        response = self.client.post(url, {
            "q": "formation à distance",
            "lat": "-11.66", "lon": "27.48", "radius_km": "25",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("lat=-11.66", response["Location"])
        self.assertIn("lon=27.48", response["Location"])
        self.assertIn("radius_km=25", response["Location"])

    def test_external_research_rejects_foreign_profile_selector(self):
        self._connect("tavily")
        response = self.api.post("/api/v1/discovery/research/", {
            "q": "formation", "profile_id": str(self.other.pk),
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_invalid_openai_output_cannot_invent_discovery_filters(self):
        self._connect("openai", model="test-model")
        with patch("intelligence.providers.openai_compatible._open_url",
                   return_value=_Reply({
                       "choices": [{
                           "message": {"content": json.dumps({
                               "vertical": "service", "place": "Atlantis",
                               "when": "tomorrow", "period": "",
                               "price": "", "text": "inventé",
                           })},
                       }],
                   })):
            response = self.api.post("/api/v1/discovery/clarify/", {
                "criteria": {"q": "quelque chose de calme avec mes amis"},
            }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["status"], "unchanged")
        self.assertEqual(response.data["data"]["query"]["q"],
                         "quelque chose de calme avec mes amis")
        self.assertNotIn("place", response.data["data"]["query"])

    def test_clarify_throttle_bounds_repeated_user_initiated_calls(self):
        # No provider needed: the budget applies before any external network.
        for _ in range(12):
            result = self.api.post("/api/v1/discovery/clarify/", {
                "criteria": {"q": "quelque chose de calme avec mes amis"},
            }, format="json")
            self.assertEqual(result.status_code, 200, result.data)
        blocked = self.api.post("/api/v1/discovery/clarify/", {
            "criteria": {"q": "quelque chose de calme avec mes amis"},
        }, format="json")
        self.assertEqual(blocked.status_code, 429)

    def test_spatial_search_does_not_reinterpret_coordinates(self):
        self._connect("openai", model="test-model")
        with patch("intelligence.providers.openai_compatible._open_url") as network:
            result = self.api.post("/api/v1/discovery/clarify/", {
                "criteria": {
                    "q": "un lieu calme",
                    "lat": "-11.66", "lon": "27.48", "radius_km": "25",
                },
            }, format="json")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["data"]["query"]["lat"], "-11.66")
        self.assertEqual(result.data["data"]["query"]["radius_km"], "25")
        self.assertEqual(result.data["data"]["status"], "already_structured")
        network.assert_not_called()


    def test_web_source_action_renders_only_sourced_leads_in_query_context(self):
        self._connect("tavily")
        self.client.force_login(self.actor)
        with patch("intelligence.providers.tavily_web._open_url",
                   return_value=_Reply({"results": [{
                       "title": "Référence externe",
                       "url": "https://example.org/reference",
                       "content": "Une information à contrôler.",
                   }]})):
            response = self.client.post(
                reverse("discovery:research"), {"q": "bourse de recherche"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Référence externe")
        self.assertContains(response, "https://example.org/reference")
        self.assertContains(response, "pistes fournies par un service externe")
        self.assertNotContains(response, "TEST-C5-KEY")
        self.assertEqual(response["Cache-Control"], "private, no-store")
