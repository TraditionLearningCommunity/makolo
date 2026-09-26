from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from automation.models import CRMWorkflow, CRMWorkflowTrigger
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus
from partners.models import Partner
from recognition.models import RewardDefinition, RewardKind
from recognition.services import get_or_create_account


class Z15OrphanScopeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="z15-s-owner", email="z15-s-owner@test.local", password="x"
        )
        self.member = User.objects.create_user(
            username="z15-s-member", email="z15-s-member@test.local", password="x"
        )
        self.other = User.objects.create_user(
            username="z15-s-other", email="z15-s-other@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="Scope A", slug="scope-a", created_by=self.owner
        )
        self.space_b = Organization.objects.create(
            name="Scope B", slug="scope-b", created_by=self.owner
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        grant_space_role(
            profile=self.owner,
            space=self.space_b,
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
        Partner.objects.create(organization=self.space, name="Partner A")
        Partner.objects.create(organization=self.space_b, name="Partner B")
        CRMWorkflow.objects.create(
            organization=self.space,
            name="Legacy membership must not authorize",
            trigger=CRMWorkflowTrigger.BIRTHDAY,
            created_by=self.owner,
        )
        self.client = APIClient()

    def test_partner_collection_can_be_space_scoped(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/v1/partners/partners/?organization={self.space.pk}"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Partner A")

    def test_automation_list_does_not_use_legacy_membership_as_authority(self):
        self.client.force_authenticate(self.member)
        response = self.client.get("/api/v1/automation/workflows/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, [])

    def test_space_recognition_is_space_scoped(self):
        account = get_or_create_account(space=self.space)
        account.points_balance = 12
        account.lifetime_earned = 12
        account.save()
        reward = RewardDefinition.objects.create(
            code="z15-space-reward",
            version=1,
            name="Reward Espace Z15",
            kind=RewardKind.OTHER,
            points_cost=5,
            beneficiary_allowed=True,
            eligibility={"beneficiary_subject_types": ["space"]},
            fulfillment={"owner_domain": "external"},
        )

        self.client.force_authenticate(self.owner)
        response = self.client.get(f"/api/v1/recognition/spaces/{self.space.pk}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["summary"]["available_credits"], 12)
        rendered = next(row for row in response.data["rewards"] if row["id"] == str(reward.pk))
        self.assertEqual(
            rendered["links"]["redeem"],
            f"/api/v1/recognition/spaces/{self.space.pk}/rewards/{reward.pk}/redeem/",
        )
        self.assertNotEqual(
            rendered["links"]["redeem"],
            f"/api/v1/recognition/rewards/{reward.pk}/redeem/",
        )

        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(f"/api/v1/recognition/spaces/{self.space.pk}/").status_code,
            404,
        )

    def test_space_trust_operator_is_not_public_operator_data(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(f"/api/v1/trust/spaces/{self.space.pk}/operator/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("issues", response.data)

        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(f"/api/v1/trust/spaces/{self.space.pk}/operator/").status_code,
            404,
        )
