"""Appuis uses the existing Loyalty owner; tests guard its member handoff."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from organizations.models import Organization
from loyalty.models import (
    LoyaltyAccount,
    LoyaltyProgram,
    LoyaltyTier,
    MembershipPlan,
    MembershipSubscription,
    MembershipStatus,
)


class AppuisProgramDepthAPITests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.member = users.objects.create_user(
            username="loyalty-appuis", password="Test-only-appuis!"
        )
        self.other = users.objects.create_user(
            username="loyalty-outsider", password="Test-only-outsider!"
        )
        self.space = Organization.objects.create(
            name="Collectif Programme", created_by=self.member,
        )
        self.program = LoyaltyProgram.objects.create(
            organization=self.space,
            created_by=self.member,
            name="Parcours fidélité communautaire",
            description="Valorise les participations",
        )
        self.tier = LoyaltyTier.objects.create(
            program=self.program,
            name="ACTIF",
            code="ACTIF",
            threshold_points=50,
            benefits="Accès aux avantages",
        )
        self.plan = MembershipPlan.objects.create(
            program=self.program,
            created_by=self.member,
            name="Adhésion gratuite",
            code="FREE",
            benefits="Participation au programme",
            price=0,
        )
        LoyaltyAccount.objects.create(
            user=self.member, program=self.program,
        )

    @property
    def url(self):
        return "/api/v1/loyalty/me/programs/" + str(self.program.pk) + "/"

    def test_member_reads_real_levels_benefits_and_free_join_capability(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        program = response.json()["program"]
        self.assertEqual(program["name"], "Parcours fidélité communautaire")
        self.assertEqual(program["tiers"][0]["benefits"], "Accès aux avantages")
        self.assertEqual(
            program["membership_plans"][0]["capabilities"], ["join"]
        )
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_unrelated_profile_cannot_read_private_member_program(self):
        self.client.force_login(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_current_membership_prevents_join_action(self):
        MembershipSubscription.objects.create(
            program=self.program, plan=self.plan, user=self.member,
            status=MembershipStatus.ACTIVE,
        )
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        program_plan = response.json()["program"]["membership_plans"][0]
        self.assertNotIn("join", program_plan.get("capabilities", []))
        self.assertEqual(response.json()["my_membership"]["status"], "active")

    def test_space_management_actions_follow_owner_permission(self):
        self.client.force_login(self.member)
        url = "/api/v1/loyalty/organizations/" + self.space.slug + "/"
        with (
            patch(
                "loyalty.api.views.user_can_view_loyalty_workspace",
                return_value=True,
            ),
            patch(
                "loyalty.api.views.user_can_manage_loyalty_strategy",
                return_value=True,
            ),
        ):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["capabilities"],
            ["create_tier", "create_plan", "create_reward"],
        )

        with (
            patch(
                "loyalty.api.views.user_can_view_loyalty_workspace",
                return_value=True,
            ),
            patch(
                "loyalty.api.views.user_can_manage_loyalty_strategy",
                return_value=False,
            ),
        ):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capabilities"], [])
        self.assertEqual(response.json()["links"], {})
