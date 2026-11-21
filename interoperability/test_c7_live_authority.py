"""C7 regression: revoking authority removes M7/Z16 reads and owner mutations."""
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User, UserProfile
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role, revoke_mandate
from authorization.platform_services import grant_platform_role
from intelligence.capabilities import IntelligenceCapability
from intelligence.models import (
    IntelligenceRoute, ProviderConnection, ProviderHealth,
    ProviderProtocol, ProviderScope,
)
from organizations.models import Organization


class C7LiveAuthorityRevocationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="c7-space-owner", password="test")
        self.manager = User.objects.create_user(username="c7-space-manager", password="test")
        self.platform = User.objects.create_user(username="c7-platform-operator", password="test")
        self.outsider = User.objects.create_user(username="c7-outsider", password="test")
        for actor in (self.owner, self.manager, self.platform, self.outsider):
            UserProfile.objects.create(user=actor)
        self.space = Organization.objects.create(
            name="C7 Space", slug="c7-space", created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        self.mandate = grant_space_role(
            profile=self.manager, space=self.space, role=SystemRoleCode.SPACE_ADMIN,
            granted_by=self.owner,
        )
        self.platform_mandate = grant_platform_role(
            profile=self.platform, role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.platform,
        )
        self.connection = ProviderConnection.objects.create(
            name="C7 Space research", scope=ProviderScope.SPACE,
            space=self.space, protocol=ProviderProtocol.TAVILY_SEARCH,
            base_url="https://api.tavily.com",
            enabled=True, health_status=ProviderHealth.UNKNOWN,
        )
        IntelligenceRoute.objects.create(
            connection=self.connection,
            capability=IntelligenceCapability.WEB_RESEARCH.value,
            enabled=True,
        )
        self.api = APIClient()
        self.z16 = "/api/v1/organizations/workspaces/c7-space/interoperability/"
        self.owner_root = "/api/v1/organizations/workspaces/c7-space/intelligence/connections/"
        self.detail = self.owner_root + str(self.connection.pk) + "/"

    def test_live_space_mandate_revocation_denies_reads_and_all_owner_mutations(self):
        self.api.force_authenticate(self.manager)
        visible = self.api.get(self.z16)
        self.assertEqual(visible.status_code, 200)
        self.assertEqual(visible["Cache-Control"], "private, no-store")
        self.assertIn(str(self.connection.pk), [
            row["id"] for row in visible.data["connections"]
        ])
        self.assertEqual(self.api.get(self.owner_root).status_code, 200)

        revoke_mandate(mandate=self.mandate, actor=self.owner)
        self.assertEqual(self.api.get(self.z16).status_code, 404)
        self.assertEqual(self.api.get(self.owner_root).status_code, 404)
        self.assertEqual(self.api.patch(
            self.detail, {"enabled": False}, format="json",
        ).status_code, 404)
        self.assertEqual(self.api.delete(self.detail).status_code, 404)
        self.connection.refresh_from_db()
        self.assertTrue(self.connection.enabled)
        self.assertTrue(ProviderConnection.objects.filter(pk=self.connection.pk).exists())

    def test_platform_mandate_does_not_grant_space_authority(self):
        self.api.force_authenticate(self.platform)
        self.assertEqual(self.api.get(self.z16).status_code, 404)
        self.assertEqual(self.api.get(self.owner_root).status_code, 404)
        self.assertEqual(self.api.delete(self.detail).status_code, 404)

    def test_live_platform_revocation_denies_projection_and_owner(self):
        self.api.force_authenticate(self.platform)
        self.assertEqual(
            self.api.get("/api/v1/platform/interoperability/").status_code, 200
        )
        self.assertEqual(
            self.api.get("/api/v1/platform/intelligence/connections/").status_code, 200
        )
        revoke_mandate(mandate=self.platform_mandate)
        self.assertEqual(
            self.api.get("/api/v1/platform/interoperability/").status_code, 403
        )
        self.assertEqual(
            self.api.get("/api/v1/platform/intelligence/connections/").status_code, 403
        )

    def test_other_actor_never_discovers_space_via_owner_detail(self):
        self.api.force_authenticate(self.outsider)
        self.assertEqual(self.api.get(self.z16).status_code, 404)
        self.assertEqual(self.api.get(self.owner_root).status_code, 404)
        self.assertEqual(self.api.patch(
            self.detail, {"api_key": "NEVER-STORE"}, format="json",
        ).status_code, 404)
        self.assertEqual(self.api.delete(self.detail).status_code, 404)
        self.assertNotIn("NEVER-STORE", str(self.api.get(self.z16).data))
