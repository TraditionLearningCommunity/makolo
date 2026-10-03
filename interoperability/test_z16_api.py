from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from accounts.models import User, UserProfile
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_space_role
from intelligence.capabilities import IntelligenceCapability
from intelligence.interoperability import authorize_provider_connection
from intelligence.models import (
    IntelligenceRoute,
    ProviderConnection,
    ProviderCredential,
    ProviderHealth,
    ProviderProtocol,
    ProviderScope,
)
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus

from .actions import ActionDefinition, ActionRegistry
from .connections import ConnectionAuthorizationError
from .extensions import ExtensionDefinition, ExtensionRegistry
from .projections import project_actions, project_extensions, project_providers, project_webhooks
from .registry import CapabilityDefinition, InteroperabilityRegistry, ProviderDefinition
from .webhooks import WebhookSubscription


class Z16RegistryProjectionTests(SimpleTestCase):
    def test_registered_contracts_project_without_runtime_objects(self):
        registry = InteroperabilityRegistry()
        registry.register_capability(CapabilityDefinition(code="notify.send", owner="notifications"))
        registry.register_provider(ProviderDefinition(code="example", capabilities={"notify.send"}))
        registry.register_adapter(provider="example", capability="notify.send", adapter=object())

        actions = ActionRegistry(registry)
        actions.register(
            ActionDefinition(
                code="notifications.send",
                capability="notify.send",
                owner="notifications",
                handler=lambda _context, _payload: None,
                authorize=lambda _context: True,
                requires_connection=True,
                idempotent=True,
            )
        )
        extensions = ExtensionRegistry(
            allowed_actions={"notifications.send"},
            allowed_events=set(),
            allowed_read_projections={"activity.public-summary"},
            allowed_ui_slots={"activity.detail.secondary"},
        )
        extensions.register(
            ExtensionDefinition(
                code="helper",
                actions={"notifications.send"},
                read_projections={"activity.public-summary"},
                ui_slots={"activity.detail.secondary"},
            )
        )

        self.assertEqual(project_providers(registry), [{
            "code": "example", "available": True, "capabilities": ["notify.send"]
        }])
        action = project_actions(actions, actor=object())[0]
        self.assertTrue(action["authorized"])
        self.assertFalse(action["available"])
        self.assertTrue(action["idempotency_required"])
        self.assertNotIn("handler", action)
        self.assertNotIn("authorize", action)
        extension = project_extensions(extensions)[0]
        self.assertNotIn("events", extension)
        self.assertEqual(extension["code"], "helper")

    def test_webhook_projection_never_exposes_endpoint_or_signing_key(self):
        subscription = WebhookSubscription(
            code="partner.activity",
            endpoint_url="https://example.test/hooks/makolo",
            event_types={"activity.published"},
            signing_key_id="secret-key-ref",
            payload_builder=lambda _event: {},
            allow_event=lambda _event: True,
        )
        row = project_webhooks([subscription], expose_event_families=True)[0]
        self.assertEqual(row["event_families"], ["activity.published"])
        self.assertNotIn("endpoint_url", row)
        self.assertNotIn("signing_key_id", row)


class Z16InteroperabilityAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="z16-owner", email="z16-owner@test.local", password="x")
        self.other = User.objects.create_user(username="z16-other", email="z16-other@test.local", password="x")
        self.member = User.objects.create_user(username="z16-member", email="z16-member@test.local", password="x")
        self.platform = User.objects.create_user(username="z16-platform", email="z16-platform@test.local", password="x")
        self.owner_profile = UserProfile.objects.create(user=self.owner)
        self.other_profile = UserProfile.objects.create(user=self.other)

        self.space = Organization.objects.create(name="Z16 Space", slug="z16-space", created_by=self.owner)
        self.other_space = Organization.objects.create(name="Z16 Other", slug="z16-other-space", created_by=self.other)
        grant_space_role(profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner)
        grant_space_role(profile=self.other, space=self.other_space, role=SystemRoleCode.SPACE_OWNER, granted_by=self.other)
        grant_platform_role(profile=self.platform, role=SystemRoleCode.PLATFORM_ADMIN, granted_by=self.platform)

        team = Team.objects.create(organization=self.space, name="Z16 team", is_active=True)
        TeamMembership.objects.create(team=team, user=self.member, status=TeamMembershipStatus.ACTIVE)

        self.profile_connection = self._connection(
            name="Personal AI", scope=ProviderScope.PROFILE, profile=self.owner_profile
        )
        self.other_profile_connection = self._connection(
            name="Other personal AI", scope=ProviderScope.PROFILE, profile=self.other_profile
        )
        self.disabled_profile_connection = self._connection(
            name="Disabled personal AI", scope=ProviderScope.PROFILE, profile=self.owner_profile, enabled=False
        )
        ProviderCredential.objects.create(
            connection=self.profile_connection, encrypted_secret="ciphertext-that-must-not-leak", key_hint="hint"
        )
        self.space_connection = self._connection(
            name="Space AI", scope=ProviderScope.SPACE, space=self.space
        )
        self.other_space_connection = self._connection(
            name="Other space AI", scope=ProviderScope.SPACE, space=self.other_space
        )
        self.platform_connection = self._connection(name="Platform AI", scope=ProviderScope.PLATFORM)
        self.client = APIClient()

    def _connection(self, *, name, scope, profile=None, space=None, enabled=True):
        connection = ProviderConnection.objects.create(
            name=name,
            protocol=ProviderProtocol.OPENAI_COMPATIBLE,
            base_url="https://provider.example.test/v1",
            default_model="test-model",
            scope=scope,
            profile=profile,
            space=space,
            enabled=enabled,
            health_status=ProviderHealth.HEALTHY,
        )
        IntelligenceRoute.objects.create(
            connection=connection,
            capability=IntelligenceCapability.TEXT_GENERATE.value,
            enabled=True,
        )
        return connection

    def test_profile_empty_lists_are_a_stable_authenticated_result(self):
        self.client.force_authenticate(self.member)
        response = self.client.get("/api/v1/me/interoperability/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["context"], "profile")
        self.assertEqual(response.data["providers"], [])
        self.assertEqual(response.data["connections"], [])
        self.assertEqual(response.data["actions"], [])
        self.assertEqual(response.data["extensions"], [])
        self.assertEqual(response.data["webhooks"], [])

    def test_profile_projection_is_owner_scoped_stable_and_secret_free(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/interoperability/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["schema_version"], "z16.v1")
        self.assertEqual(response.data["context"], "profile")
        self.assertEqual(response.data["providers"], [])
        self.assertEqual(response.data["actions"], [])
        self.assertEqual(response.data["extensions"], [])
        self.assertEqual(response.data["webhooks"], [])
        ids = {row["id"] for row in response.data["connections"]}
        self.assertIn(str(self.profile_connection.pk), ids)
        self.assertIn(str(self.disabled_profile_connection.pk), ids)
        self.assertNotIn(str(self.other_profile_connection.pk), ids)
        serialized = response.content.decode("utf-8")
        self.assertNotIn("ciphertext-that-must-not-leak", serialized)
        self.assertNotIn("key_hint", serialized)
        self.assertNotIn("base_url", serialized)
        disabled = next(row for row in response.data["connections"] if row["id"] == str(self.disabled_profile_connection.pk))
        self.assertFalse(disabled["usable"])
        self.assertTrue(disabled["manageable"])
        self.assertFalse(disabled["permissions"]["use"])
        self.assertTrue(disabled["permissions"]["manage"])

    def test_profile_a_never_sees_profile_b_connection(self):
        self.client.force_authenticate(self.other)
        response = self.client.get("/api/v1/me/interoperability/")
        self.assertEqual(response.status_code, 200, response.data)
        ids = {row["id"] for row in response.data["connections"]}
        self.assertEqual(ids, {str(self.other_profile_connection.pk)})

    def test_space_projection_requires_direct_space_manage_authority(self):
        url = "/api/v1/organizations/workspaces/z16-space/interoperability/"
        self.client.force_authenticate(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["context"], "space")
        self.assertEqual(
            {row["id"] for row in response.data["connections"]},
            {str(self.space_connection.pk)},
        )

        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_authenticate(self.platform)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_platform_projection_only_contains_platform_connections(self):
        self.client.force_authenticate(self.platform)
        response = self.client.get("/api/v1/platform/interoperability/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["context"], "platform")
        self.assertFalse(response.data["space_modules_included"])
        self.assertFalse(response.data["personal_modules_included"])
        self.assertEqual(
            {row["id"] for row in response.data["connections"]},
            {str(self.platform_connection.pk)},
        )
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get("/api/v1/platform/interoperability/").status_code, 403)

    def test_explicit_space_connection_authorizer_does_not_inherit_platform(self):
        with self.assertRaises(ConnectionAuthorizationError):
            authorize_provider_connection(actor=self.platform, connection=self.space_connection)
        with self.assertRaises(ConnectionAuthorizationError):
            authorize_provider_connection(actor=self.member, connection=self.space_connection)
        authorize_provider_connection(actor=self.owner, connection=self.space_connection)
