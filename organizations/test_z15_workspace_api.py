from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_space_role
from core.capabilities import get_web_capabilities
from organizations.console_context import authorized_spaces
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus
from scanner.models import ScannerAssignment


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

    def test_membership_only_does_not_open_space_workspace_or_space_analytics(self):
        self.client.force_authenticate(self.member)
        response = self.client.get("/api/v1/organizations/workspaces/z15-space/")
        self.assertEqual(response.status_code, 404)
        analytics = self.client.get(
            "/api/v1/analytics/overview/?organization=z15-space"
        )
        self.assertEqual(analytics.status_code, 404)

    def test_scanner_assignment_is_responsibility_not_space_authority(self):
        activity = Activity.objects.create(
            title="Contrôle Z15",
            slug="controle-z15",
            created_by=self.owner,
            space=self.space,
        )
        ScannerAssignment.objects.create(
            activity=activity,
            agent=self.member,
            assigned_by=self.owner,
            label="Porte Z15",
        )

        self.client.force_authenticate(self.member)
        self.assertEqual(
            self.client.get("/api/v1/organizations/workspaces/z15-space/").status_code,
            404,
        )
        self.assertFalse(authorized_spaces(self.member).filter(pk=self.space.pk).exists())
        current = self.client.get("/api/v1/scanner/assignments/current/")
        self.assertEqual(current.status_code, 200, current.data)
        self.assertEqual(current.data["count"], 1)
        self.assertEqual(len(current.data["results"]), 1)
        self.assertEqual(str(current.data["results"][0]["id"]), str(
            ScannerAssignment.objects.get(activity=activity, agent=self.member).pk
        ))

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
        self.assertFalse(
            authorized_spaces(self.platform).filter(pk=self.space.pk).exists()
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
        analytics = self.client.get(
            "/api/v1/analytics/overview/?organization=z15-space"
        )
        self.assertEqual(analytics.status_code, 200, analytics.data)
        self.assertEqual(analytics.data["event_cards"], [])
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

        platform_caps = get_web_capabilities(self.platform)
        self.assertFalse(platform_caps["has_organizer_tools"])
        self.assertFalse(platform_caps["has_organization"])
        self.assertTrue(platform_caps["can_access_operations"])
        self.assertTrue(platform_caps["can_curate_opportunities"])

        owner_caps = get_web_capabilities(self.owner)
        self.assertTrue(owner_caps["has_organizer_tools"])
        self.assertTrue(owner_caps["has_organization"])
