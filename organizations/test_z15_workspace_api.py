from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import can, grant_activity_role, grant_space_role, revoke_mandate
from core.capabilities import get_web_capabilities
from organizations.console_context import authorized_spaces
from organizations.models import Organization, SpaceArchetype, SpaceLifecycle, Team, TeamMembership, TeamMembershipStatus
from groups.models import Group, GroupMembership
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


    def test_workspace_projection_exposes_mobile_space_contract_without_private_mandates(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/organizations/workspaces/z15-space/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["space"]["archetype"], SpaceArchetype.GENERIC)
        self.assertEqual(response.data["space"]["lifecycle"], SpaceLifecycle.ACTIVE)
        self.assertIn("operating_preset", response.data)
        self.assertIn("operational_footprint", response.data)
        self.assertIn("team_summary", response.data)
        self.assertIn("ownership_summary", response.data)
        self.assertNotIn("mandates", response.data)

    def test_workspace_patch_changes_archetype_without_destroying_activity(self):
        activity = Activity.objects.create(
            title="Verticale conservée",
            slug="verticale-conservee",
            created_by=self.owner,
            space=self.space,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            "/api/v1/organizations/workspaces/z15-space/",
            {"archetype": SpaceArchetype.EDUCATION},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.space.refresh_from_db()
        self.assertEqual(self.space.archetype, SpaceArchetype.EDUCATION)
        self.assertTrue(self.space.activities.filter(pk=activity.pk).exists())

    def test_membership_only_cannot_patch_workspace(self):
        self.client.force_authenticate(self.member)
        response = self.client.patch(
            "/api/v1/organizations/workspaces/z15-space/",
            {"archetype": SpaceArchetype.COMMERCE},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_archive_and_restore_through_online_api(self):
        self.client.force_authenticate(self.owner)
        archived = self.client.post(
            "/api/v1/organizations/workspaces/z15-space/archive/",
            {},
            format="json",
        )
        self.assertEqual(archived.status_code, 200, archived.data)
        self.assertEqual(archived.data["space"]["lifecycle"], SpaceLifecycle.ARCHIVED)
        restored = self.client.post(
            "/api/v1/organizations/workspaces/z15-space/restore/",
            {},
            format="json",
        )
        self.assertEqual(restored.status_code, 200, restored.data)
        self.assertEqual(restored.data["space"]["lifecycle"], SpaceLifecycle.ACTIVE)

    def test_workspace_create_grants_owner_and_active_lifecycle(self):
        user = User.objects.create_user(
            username="z15-create",
            email="z15-create@test.local",
            password="x",
        )
        self.client.force_authenticate(user)
        response = self.client.post(
            "/api/v1/organizations/workspaces/",
            {"name": "Created Mobile Space", "archetype": SpaceArchetype.COMMERCE},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        created = Organization.objects.get(pk=response.data["space"]["id"])
        self.assertEqual(created.lifecycle, SpaceLifecycle.ACTIVE)
        self.assertEqual(created.archetype, SpaceArchetype.COMMERCE)
        self.assertTrue(can(user, PermissionCode.SPACE_OWNERSHIP_MANAGE, created))


    def test_team_api_requires_team_permission_and_updates_canonical_responsibility(self):
        target = User.objects.create_user(
            username="z15-team-target",
            email="z15-team-target@test.local",
            password="x",
        )
        self.client.force_authenticate(self.owner)
        created = self.client.post(
            "/api/v1/organizations/workspaces/z15-space/team/",
            {"email": target.email, "role": SystemRoleCode.FINANCE},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        membership_id = created.data["id"]
        updated = self.client.patch(
            f"/api/v1/organizations/workspaces/z15-space/team/{membership_id}/",
            {"role": SystemRoleCode.MARKETING},
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertTrue(can(target, PermissionCode.MARKETING_MANAGE, self.space))
        self.assertFalse(can(target, PermissionCode.FINANCE_VIEW, self.space))

        self.client.force_authenticate(self.member)
        self.assertEqual(
            self.client.get("/api/v1/organizations/workspaces/z15-space/team/").status_code,
            404,
        )


    def test_workspace_requires_authentication(self):
        response = self.client.get("/api/v1/organizations/workspaces/")
        self.assertIn(response.status_code, {401, 403})

    def test_activity_mandate_opens_limited_space_and_scoped_responsibility(self):
        activity = Activity.objects.create(
            title="Départ Lubumbashi → Kolwezi",
            slug="depart-lubumbashi-kolwezi",
            created_by=self.owner,
            space=self.space,
        )
        activity_user = User.objects.create_user(
            username="zs1-activity", email="zs1-activity@test.local", password="x"
        )
        grant_activity_role(
            profile=activity_user,
            activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SCANNER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(activity_user)
        response = self.client.get("/api/v1/organizations/workspaces/z15-space/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["authority"]["scope"], "activity_limited")
        self.assertEqual(response.data["responsibilities"][0]["scope"], "activity_limited")
        self.assertTrue(response.data["authority"]["limited_to_activities"])
        scoped = [row for row in response.data["responsibilities"] if row["scope"] == "activity"]
        self.assertEqual(len(scoped), 1)
        self.assertEqual(scoped[0]["activity"]["title"], "Départ Lubumbashi → Kolwezi")
        self.assertNotIn("operational_footprint", response.data)
        self.assertNotIn("team_summary", response.data)
        self.assertNotIn("ownership_summary", response.data)

    def test_group_membership_only_does_not_open_space(self):
        group = Group.objects.create(
            name="Groupe ZS1",
            space=self.space,
            created_by=self.owner,
        )
        GroupMembership.objects.create(group=group, profile=self.member)
        self.client.force_authenticate(self.member)
        self.assertEqual(
            self.client.get("/api/v1/organizations/workspaces/z15-space/").status_code,
            404,
        )

    def test_responsibilities_are_current_space_only_and_not_permission_dump(self):
        other = Organization.objects.create(
            name="Other ZS1", slug="other-zs1", created_by=self.owner
        )
        grant_space_role(
            profile=self.owner,
            space=other,
            role=SystemRoleCode.FINANCE,
            granted_by=self.owner,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/organizations/workspaces/z15-space/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["responsibilities"][0]["label"], "Toutes mes responsabilités")
        serialized = str(response.data)
        self.assertNotIn("other-zs1", serialized)
        self.assertNotIn("permissions", serialized.lower())

    def test_all_archetypes_expose_primary_business_language(self):
        expected = {
            SpaceArchetype.GENERIC: "Activités",
            SpaceArchetype.CREATIVE: "Créations",
            SpaceArchetype.MEDIA: "Productions",
            SpaceArchetype.EDUCATION: "Programmes",
            SpaceArchetype.COMMERCE: "Commerce",
            SpaceArchetype.SERVICE_PROVIDER: "Prestations",
            SpaceArchetype.TRANSPORT_OPERATOR: "Transport",
            SpaceArchetype.COMMUNITY: "Initiatives",
        }
        self.client.force_authenticate(self.owner)
        for archetype, label in expected.items():
            self.space.archetype = archetype
            self.space.save(update_fields=["archetype", "updated_at"])
            response = self.client.get("/api/v1/organizations/workspaces/z15-space/")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(
                response.data["operating_preset"]["primary_business_label"],
                label,
            )

    def test_workspace_capability_does_not_survive_revoked_mandate(self):
        admin = User.objects.create_user(
            username="zs1-admin", email="zs1-admin@test.local", password="x"
        )
        mandate = grant_space_role(
            profile=admin,
            space=self.space,
            role=SystemRoleCode.SPACE_ADMIN,
            granted_by=self.owner,
        )
        self.client.force_authenticate(admin)
        before = self.client.get("/api/v1/organizations/workspaces/z15-space/")
        self.assertEqual(before.status_code, 200, before.data)
        self.assertTrue(before.data["capabilities"]["update_space"])
        revoke_mandate(mandate=mandate, actor=self.owner)
        after = self.client.patch(
            "/api/v1/organizations/workspaces/z15-space/",
            {"name": "Should not change"},
            format="json",
        )
        self.assertEqual(after.status_code, 404)
        self.space.refresh_from_db()
        self.assertEqual(self.space.name, "Z15 Space")
