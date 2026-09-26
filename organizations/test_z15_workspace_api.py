from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_space_role
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus


class Z15WorkspaceContractTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="z15-owner", email="z15-owner@test.local", password="x"
        )
        self.member = User.objects.create_user(
            username="z15-member", email="z15-member@test.local", password="x"
        )
        self.platform = User.objects.create_user(
            username="z15-platform", email="z15-platform@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="Z15 Space", slug="z15-space", created_by=self.owner
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        team = Team.objects.create(
            organization=self.space,
            name="Collaborateurs Z15",
            is_active=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=self.member,
            status=TeamMembershipStatus.ACTIVE,
        )
        grant_platform_role(
            profile=self.platform,
            role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.platform,
        )
        self.client = APIClient()

    def test_space_workspace_is_mandate_scoped_and_excludes_platform(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/organizations/workspaces/z15-space/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["platform_modules_included"])
        keys = {row["key"] for row in response.data["modules"]}
        self.assertIn("partners", keys)
        self.assertIn("recognition", keys)
        self.assertIn("trust", keys)
        self.assertIn("funding", keys)

    def test_legacy_membership_does_not_open_space_workspace(self):
        self.client.force_authenticate(self.member)
        response = self.client.get("/api/v1/organizations/workspaces/z15-space/")
        self.assertEqual(response.status_code, 404)

    def test_platform_contract_is_separate(self):
        self.client.force_authenticate(self.platform)
        self.assertEqual(
            self.client.get("/api/v1/organizations/workspaces/z15-space/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/api/v1/organizations/workspaces/").data,
            [],
        )
        self.assertEqual(
            self.client.get(f"/api/v1/recognition/spaces/{self.space.pk}/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/trust/spaces/{self.space.pk}/operator/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/funding/?space={self.space.pk}").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/analytics/overview/?organization={self.space.slug}"
            ).status_code,
            404,
        )

        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.get("/api/v1/platform/capabilities/").status_code,
            403,
        )

        self.client.force_authenticate(self.platform)
        response = self.client.get("/api/v1/platform/capabilities/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["context"], "platform")
        self.assertFalse(response.data["space_modules_included"])
        self.assertTrue(
            any(row["key"] == "operations" for row in response.data["modules"])
        )
