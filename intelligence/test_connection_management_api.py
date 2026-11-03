"""Targeted C4 contracts: secret lifecycle, scope isolation and existing Z16 consumption."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserProfile
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_space_role
from intelligence.capabilities import IntelligenceCapability
from intelligence.contracts import IntelligenceRequest
from intelligence.gateway import IntelligenceGateway
from intelligence.runtime import build_runtime_registry
from intelligence.credentials import get_provider_secret
from intelligence.models import ProviderConnection, ProviderCredential, ProviderHealth, ProviderScope
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus
from operations.models import OperationsAuditLog


@patch.dict("os.environ", {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "unit-only-c4-master-key"})
class ConnectionManagementAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="c4-owner", email="c4-owner@example.test", password="test",
        )
        self.other = User.objects.create_user(
            username="c4-other", email="c4-other@example.test", password="test",
        )
        self.member = User.objects.create_user(
            username="c4-member", email="c4-member@example.test", password="test",
        )
        self.platform = User.objects.create_user(
            username="c4-platform", email="c4-platform@example.test", password="test",
        )
        self.owner_profile = UserProfile.objects.create(user=self.owner)
        self.other_profile = UserProfile.objects.create(user=self.other)
        self.space = Organization.objects.create(
            name="C4 Space", slug="c4-space", created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        grant_platform_role(
            profile=self.platform, role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.platform,
        )
        team = Team.objects.create(organization=self.space, name="C4 team", is_active=True)
        TeamMembership.objects.create(team=team, user=self.member, status=TeamMembershipStatus.ACTIVE)
        self.client = APIClient()
        self.profile_url = "/api/v1/me/intelligence/connections/"
        self.space_url = "/api/v1/organizations/workspaces/c4-space/intelligence/connections/"
        self.platform_url = "/api/v1/platform/intelligence/connections/"

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _create(self, url, *, key="C4-PRIVATE-KEY", name="Mon moteur Web"):
        return self.client.post(url, {
            "provider": "tavily", "name": name, "api_key": key, "consent": True,
        }, format="json")

    def test_catalog_and_profile_lifecycle_are_real_but_secret_free(self):
        self._auth(self.owner)
        catalog = self.client.get(self.profile_url)
        self.assertEqual(catalog.status_code, 200)
        self.assertTrue(any(offer["code"] == "tavily" and offer["can_connect"]
                            for offer in catalog.data["offers"]))
        response = self._create(self.profile_url)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertNotIn("C4-PRIVATE-KEY", str(response.data))
        self.assertNotIn("api.tavily.com", str(response.data))
        identity = response.data["id"]
        connection = ProviderConnection.objects.get(pk=identity)
        self.assertEqual(connection.scope, ProviderScope.PROFILE)
        self.assertEqual(connection.profile, self.owner_profile)
        self.assertEqual(get_provider_secret(connection=connection), "C4-PRIVATE-KEY")
        self.assertEqual([row.capability for row in connection.routes.all()], ["web_research"])

        z16 = self.client.get("/api/v1/me/interoperability/")
        self.assertEqual(z16.status_code, 200)
        self.assertIn(identity, [row["id"] for row in z16.data["connections"]])
        self.assertNotIn("C4-PRIVATE-KEY", str(z16.data))
        self.assertNotIn("api.tavily.com", str(z16.data))

        detail = self.profile_url + identity + "/"
        disabled = self.client.patch(detail, {"enabled": False}, format="json")
        self.assertEqual(disabled.status_code, 200, disabled.data)
        self.assertFalse(disabled.data["usable"])
        replaced = self.client.patch(detail, {"api_key": "NEW-SECRET"}, format="json")
        self.assertEqual(replaced.status_code, 200, replaced.data)
        connection.refresh_from_db()
        self.assertEqual(get_provider_secret(connection=connection), "NEW-SECRET")
        self.assertNotIn("NEW-SECRET", str(replaced.data))
        enabled = self.client.patch(detail, {"enabled": True}, format="json")
        self.assertEqual(enabled.status_code, 200, enabled.data)
        removed = self.client.delete(detail)
        self.assertEqual(removed.status_code, 204)
        self.assertFalse(ProviderConnection.objects.filter(pk=identity).exists())
        self.assertFalse(ProviderCredential.objects.filter(connection_id=identity).exists())
        self.assertEqual(self.client.get(detail).status_code, 404)
        records = list(OperationsAuditLog.objects.filter(
            target_type="provider_connection", target_id=identity,
        ))
        self.assertEqual({row.action for row in records}, {
            "intelligence.connection_created",
            "intelligence.connection_updated",
            "intelligence.connection_removed",
        })
        for row in records:
            recorded = str((row.before, row.after, row.metadata, row.summary))
            self.assertNotIn("C4-PRIVATE-KEY", recorded)
            self.assertNotIn("NEW-SECRET", recorded)
            self.assertNotIn("api.tavily.com", recorded)


    def test_created_openai_provider_executes_through_existing_gateway_without_real_network(self):
        self._auth(self.owner)
        created = self.client.post(self.profile_url, {
            "provider": "openai",
            "name": "Génération de test",
            "api_key": "TEST-ONLY-OPENAI-KEY",
            "model": "test-model",
            "consent": True,
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)

        class FakeProviderResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return b'{"choices":[{"message":{"content":"C4 OK"}}]}'

        capability = IntelligenceCapability.TEXT_GENERATE
        registry = build_runtime_registry(
            capability=capability, profile=self.owner_profile,
        )
        with patch(
            "intelligence.providers.openai_compatible._open_url",
            return_value=FakeProviderResponse(),
        ) as provider_transport:
            result = IntelligenceGateway(registry).execute(
                IntelligenceRequest(
                    capability=capability,
                    input={"text": "Vérification C4"},
                )
            )
        self.assertTrue(result.available)
        self.assertEqual(result.output, "C4 OK")
        self.assertEqual(result.provider_key, created.data["id"])
        transport_request = provider_transport.call_args.args[0]
        self.assertEqual(
            transport_request.get_header("Authorization"),
            "Bearer TEST-ONLY-OPENAI-KEY",
        )
        self.assertNotIn("TEST-ONLY-OPENAI-KEY", str(created.data))

    def test_reactivation_and_rotation_invalidate_stale_health_checks(self):
        self._auth(self.owner)
        response = self._create(self.profile_url, name="Health reset")
        self.assertEqual(response.status_code, 201)
        connection = ProviderConnection.objects.get(pk=response.data["id"])
        connection.health_status = ProviderHealth.HEALTHY
        connection.last_checked_at = timezone.now()
        connection.last_latency_ms = 19
        connection.save(update_fields=[
            "health_status", "last_checked_at", "last_latency_ms",
        ])
        detail = self.profile_url + str(connection.pk) + "/"
        self.assertEqual(
            self.client.patch(detail, {"enabled": False}, format="json").status_code, 200,
        )
        restored = self.client.patch(detail, {"enabled": True}, format="json")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.data["health"], "unknown")
        connection.refresh_from_db()
        self.assertIsNone(connection.last_checked_at)
        self.assertIsNone(connection.last_latency_ms)
        connection.health_status = ProviderHealth.HEALTHY
        connection.last_checked_at = timezone.now()
        connection.last_latency_ms = 34
        connection.save(update_fields=[
            "health_status", "last_checked_at", "last_latency_ms",
        ])
        rotated = self.client.patch(detail, {"api_key": "replacement"}, format="json")
        self.assertEqual(rotated.status_code, 200)
        self.assertEqual(rotated.data["health"], "unknown")
        connection.refresh_from_db()
        self.assertIsNone(connection.last_checked_at)
        self.assertIsNone(connection.last_latency_ms)

    def test_owner_scoped_connection_is_consumable_by_existing_runtime_registry(self):
        self._auth(self.owner)
        created = self._create(self.profile_url)
        self.assertEqual(created.status_code, 201, created.data)
        identity = created.data["id"]
        capability = IntelligenceCapability.WEB_RESEARCH

        personal = build_runtime_registry(capability=capability, profile=self.owner_profile)
        other = build_runtime_registry(capability=capability, profile=self.other_profile)
        self.assertEqual([provider.key for provider in personal.providers], [identity])
        self.assertEqual(other.providers, [])

        detail = self.profile_url + identity + "/"
        self.assertEqual(
            self.client.patch(detail, {"enabled": False}, format="json").status_code, 200,
        )
        disabled = build_runtime_registry(capability=capability, profile=self.owner_profile)
        self.assertEqual(disabled.providers, [])

        self.assertEqual(
            self.client.patch(detail, {"enabled": True}, format="json").status_code, 200,
        )
        enabled = build_runtime_registry(capability=capability, profile=self.owner_profile)
        self.assertEqual([provider.key for provider in enabled.providers], [identity])

        self.assertEqual(self.client.delete(detail).status_code, 204)
        removed = build_runtime_registry(capability=capability, profile=self.owner_profile)
        self.assertEqual(removed.providers, [])

    def test_consent_cannot_be_inferred_from_a_submitted_api_key(self):
        self._auth(self.owner)
        response = self.client.post(self.profile_url, {
            "provider": "tavily",
            "name": "Sans consentement",
            "api_key": "NOT-STORED",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProviderConnection.objects.filter(name="Sans consentement").count(), 0)

    def test_cross_profile_is_404_even_for_platform_operator(self):
        self._auth(self.owner)
        created = self._create(self.profile_url)
        self.assertEqual(created.status_code, 201)
        detail = self.profile_url + created.data["id"] + "/"
        for unauthorized in (self.other, self.platform):
            self._auth(unauthorized)
            self.assertEqual(self.client.get(detail).status_code, 404)
            self.assertEqual(
                self.client.patch(detail, {"enabled": False}, format="json").status_code, 404,
            )
            self.assertEqual(self.client.delete(detail).status_code, 404)

    def test_rejects_arbitrary_endpoint_duplicate_and_invalid_secret(self):
        self._auth(self.owner)
        rejected = self.client.post(self.profile_url, {
            "provider": "tavily", "name": "Malicious",
            "api_key": "private-key", "base_url": "https://private.invalid", "consent": True,
        }, format="json")
        self.assertEqual(rejected.status_code, 400)
        self.assertFalse(ProviderConnection.objects.filter(name="Malicious").exists())
        self.assertEqual(self._create(self.profile_url).status_code, 201)
        self.assertEqual(self._create(self.profile_url).status_code, 400)
        self.assertEqual(self._create(self.profile_url, key="  ", name="Empty").status_code, 400)

    def test_space_requires_direct_mandate_not_membership_or_platform(self):
        for unauthorized in (self.member, self.other, self.platform):
            self._auth(unauthorized)
            self.assertEqual(self.client.get(self.space_url).status_code, 404)
            self.assertEqual(self._create(self.space_url).status_code, 404)
        self._auth(self.owner)
        response = self._create(self.space_url, name="Moteur Space")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(ProviderConnection.objects.get(pk=response.data["id"]).space, self.space)
        self.assertEqual(self.client.get(
            "/api/v1/organizations/workspaces/c4-space/interoperability/",
        ).status_code, 200)
        self._auth(self.member)
        self.assertEqual(
            self.client.delete(self.space_url + response.data["id"] + "/").status_code, 404,
        )

    def test_platform_only_manages_own_scope(self):
        self._auth(self.owner)
        self.assertEqual(self.client.get(self.platform_url).status_code, 403)
        self.assertEqual(self._create(self.platform_url).status_code, 403)
        self._auth(self.platform)
        response = self._create(self.platform_url, name="Moteur Platform")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(ProviderConnection.objects.get(pk=response.data["id"]).scope,
                         ProviderScope.PLATFORM)
        self.assertEqual(
            self.client.get("/api/v1/platform/interoperability/").status_code, 200,
        )

    def test_missing_server_encryption_config_never_stores_plain_key(self):
        self._auth(self.owner)
        with patch.dict("os.environ", {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": ""}):
            offers = self.client.get(self.profile_url)
            self.assertTrue(all(not item["can_connect"] for item in offers.data["offers"]))
            self.assertEqual(self._create(self.profile_url).status_code, 503)
        self.assertFalse(ProviderConnection.objects.filter(name="Mon moteur Web").exists())
