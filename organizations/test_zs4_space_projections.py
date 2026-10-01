from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from crm.canonical_models import Audience
from crm.models import CRMContact
from groups.models import Group, GroupMembership, GroupMembershipStatus
from organizations.models import (
    Organization,
    SpaceArchetype,
    Team,
    TeamMembership,
    TeamMembershipStatus,
)
from partners.models import Partner


class ZS4SpaceProjectionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="zs4-owner", email="zs4-owner@test.local", password="x"
        )
        self.outsider = User.objects.create_user(
            username="zs4-outsider", email="zs4-outsider@test.local", password="x"
        )
        self.member = User.objects.create_user(
            username="zs4-member", email="zs4-member@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="ZS4 Space",
            slug="zs4-space",
            archetype=SpaceArchetype.COMMERCE,
            created_by=self.owner,
        )
        self.owner_mandate = grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        self.team = Team.objects.create(
            organization=self.space,
            name="Équipe principale",
            is_default=True,
            is_active=True,
        )
        self.owner_membership = TeamMembership.objects.create(
            team=self.team,
            user=self.owner,
            status=TeamMembershipStatus.ACTIVE,
        )
        self.member_membership = TeamMembership.objects.create(
            team=self.team,
            user=self.member,
            status=TeamMembershipStatus.ACTIVE,
        )
        self.client = APIClient()

    def test_authentication_and_outsider_minimal_disclosure(self):
        for suffix in ("us", "relationships", "pilot"):
            anonymous = self.client.get(
                f"/api/v1/organizations/workspaces/{self.space.slug}/{suffix}/"
            )
            self.assertIn(anonymous.status_code, {401, 403})

        self.client.force_authenticate(self.outsider)
        for suffix in ("us", "relationships", "pilot"):
            response = self.client.get(
                f"/api/v1/organizations/workspaces/{self.space.slug}/{suffix}/"
            )
            self.assertEqual(response.status_code, 404)

    def test_us_is_human_collective_projection_not_settings_dump(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["identity"]["id"], str(self.space.pk))
        self.assertEqual(response.data["identity"]["name"], self.space.name)
        self.assertEqual(response.data["authority"]["scope"], "space")
        self.assertEqual(response.data["team"]["active_members"], 2)
        self.assertTrue(response.data["capabilities"]["manage_team"])
        self.assertTrue(response.data["capabilities"]["manage_ownership"])
        self.assertEqual(len(response.data["ownership"]["items"]), 1)
        self.assertNotIn("permissions", response.data)
        self.assertNotIn("subscription_id", response.data)

    def test_team_membership_alone_never_opens_zs4(self):
        self.client.force_authenticate(self.member)
        for suffix in ("us", "relationships", "pilot"):
            response = self.client.get(
                f"/api/v1/organizations/workspaces/{self.space.slug}/{suffix}/"
            )
            self.assertEqual(response.status_code, 404)

    def test_activity_only_authority_is_strictly_limited(self):
        activity = Activity.objects.create(
            title="Départ ZS4",
            slug="depart-zs4",
            created_by=self.owner,
            space=self.space,
        )
        scoped = User.objects.create_user(
            username="zs4-scoped", email="zs4-scoped@test.local", password="x"
        )
        grant_activity_role(
            profile=scoped,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(scoped)

        us = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
        )
        self.assertEqual(us.status_code, 200, us.data)
        self.assertEqual(us.data["authority"]["scope"], "activity_limited")
        self.assertEqual(us.data["team"]["items"], [])
        self.assertEqual(us.data["ownership"]["items"], [])
        self.assertNotIn("contact_email", us.data["identity"])

        relations = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/relationships/"
        )
        self.assertEqual(relations.status_code, 200, relations.data)
        self.assertEqual(relations.data["sections"], {})

        pilot = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/pilot/"
        )
        self.assertEqual(pilot.status_code, 200, pilot.data)
        self.assertEqual(pilot.data["sections"], {})
        self.assertFalse(pilot.data["capabilities"]["view_analytics"])

    def test_relationships_keep_owner_types_and_same_profile_provenance(self):
        group = Group.objects.create(
            name="Clients premium",
            slug="clients-premium",
            space=self.space,
            created_by=self.owner,
        )
        GroupMembership.objects.create(
            group=group,
            profile=self.member,
            status=GroupMembershipStatus.ACTIVE,
        )
        contact = CRMContact.objects.create(
            organization=self.space,
            user=self.member,
            email=self.member.email,
            name="Membre CRM",
        )
        Audience.objects.create(
            organization=self.space,
            name="Public actif",
            created_by=self.owner,
        )
        partner = Partner.objects.create(
            organization=self.space,
            user=self.member,
            name="Partenaire ZS4",
            created_by=self.owner,
        )

        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/relationships/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["label"], "Clients & relations")
        self.assertEqual(
            {
                "team",
                "groups",
                "crm_contacts",
                "audiences",
                "partners",
            },
            set(response.data["sections"]),
        )
        self.assertEqual(
            response.data["sections"]["crm_contacts"]["items"][0]["id"],
            str(contact.pk),
        )
        self.assertEqual(
            response.data["sections"]["partners"]["items"][0]["id"],
            str(partner.pk),
        )
        self.assertEqual(
            response.data["sections"]["crm_contacts"]["items"][0]["profile"]["id"],
            str(self.member.pk),
        )
        self.assertEqual(
            response.data["sections"]["partners"]["items"][0]["profile"]["id"],
            str(self.member.pk),
        )
        crm_row = response.data["sections"]["crm_contacts"]["items"][0]
        self.assertNotIn("email", crm_row)
        self.assertNotIn("phone", crm_row)
        self.assertNotIn("marketing_consent", crm_row)

    def test_relationship_language_consumes_all_eight_archetypes(self):
        expected = {
            SpaceArchetype.GENERIC: "Personnes & relations",
            SpaceArchetype.CREATIVE: "Publics & partenaires",
            SpaceArchetype.MEDIA: "Publics & partenaires",
            SpaceArchetype.EDUCATION: "Groupes, personnes & partenaires",
            SpaceArchetype.COMMERCE: "Clients & relations",
            SpaceArchetype.SERVICE_PROVIDER: "Clients & partenaires",
            SpaceArchetype.TRANSPORT_OPERATOR: "Relations",
            SpaceArchetype.COMMUNITY: "Communauté & partenaires",
        }
        for index, (archetype, label) in enumerate(expected.items()):
            space = Organization.objects.create(
                name=f"ZS4 Archetype {index}",
                slug=f"zs4-archetype-{index}",
                archetype=archetype,
                created_by=self.owner,
            )
            grant_space_role(
                profile=self.owner,
                space=space,
                role=SystemRoleCode.SPACE_OWNER,
                granted_by=self.owner,
            )
            self.client.force_authenticate(self.owner)
            response = self.client.get(
                f"/api/v1/organizations/workspaces/{space.slug}/relationships/"
            )
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["label"], label)

    def test_pilot_preserves_zero_and_insufficient_data_without_fake_signal(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/pilot/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        analytics = response.data["sections"]["analytics"]
        self.assertEqual(analytics["state"], "insufficient_data")
        events = next(
            row for row in analytics["metrics"] if row["key"] == "events_count"
        )
        self.assertEqual(events["state"], "known")
        self.assertEqual(events["value"], "0")
        attendance = next(
            row for row in analytics["metrics"] if row["key"] == "attendance_percent"
        )
        self.assertEqual(attendance["state"], "insufficient_data")
        self.assertIsNone(attendance["value"])
        self.assertEqual(response.data["signals"], [])
        self.assertNotIn("health_score", response.data)
        self.assertNotIn("performance_score", response.data)

    def test_platform_authority_does_not_open_space_pilot(self):
        platform = User.objects.create_user(
            username="zs4-platform", email="zs4-platform@test.local", password="x"
        )
        grant_platform_role(
            profile=platform,
            role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=platform,
        )
        self.client.force_authenticate(platform)
        response = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/pilot/"
        )
        self.assertEqual(response.status_code, 404)

    def test_read_capability_is_not_authorization_token(self):
        admin = User.objects.create_user(
            username="zs4-admin", email="zs4-admin@test.local", password="x"
        )
        mandate = grant_space_role(
            profile=admin,
            space=self.space,
            role=SystemRoleCode.SPACE_ADMIN,
            granted_by=self.owner,
        )
        self.client.force_authenticate(admin)
        projection = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
        )
        self.assertEqual(projection.status_code, 200, projection.data)
        self.assertTrue(projection.data["capabilities"]["manage_team"])

        revoke_mandate(mandate=mandate, actor=self.owner)
        mutation = self.client.post(
            f"/api/v1/organizations/workspaces/{self.space.slug}/team/",
            {"email": "new-team@test.local", "role": SystemRoleCode.FINANCE},
            format="json",
        )
        self.assertEqual(mutation.status_code, 404)
