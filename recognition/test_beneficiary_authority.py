from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from organizations.models import Organization

from .economy import redeem_reward
from .models import RewardDefinition
from .services import get_or_create_account


class RecognitionBeneficiaryAuthorityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="recognition-benefit-owner",
            email="recognition-benefit-owner@example.test",
            password="Recognition-2026!",
        )
        self.actor = User.objects.create_user(
            username="recognition-benefit-space-actor",
            email="recognition-benefit-space-actor@example.test",
            password="Recognition-2026!",
        )
        self.outsider = User.objects.create_user(
            username="recognition-benefit-outsider",
            email="recognition-benefit-outsider@example.test",
            password="Recognition-2026!",
        )
        self.space = Organization.objects.create(name="Beneficiary Space", created_by=self.actor)
        grant_space_role(
            profile=self.actor,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.actor,
            source="recognition-k-test",
        )
        self.account = get_or_create_account(profile=self.owner)
        self.account.points_balance = 100
        self.account.lifetime_earned = 100
        self.account.save()
        self.reward = RewardDefinition.objects.create(
            code="space-benefit-consent",
            version=1,
            name="Bénéfice Espace",
            points_cost=20,
            beneficiary_allowed=True,
            acceptance_required=True,
        )
        self.redemption = redeem_reward(
            owner_account=self.account,
            reward=self.reward,
            idempotency_key="space-benefit-consent-1",
            actor_profile=self.owner,
            beneficiary_space=self.space,
        )

    def test_membershipless_outsider_cannot_decide_for_space(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse(
                "recognition:redemption-decision",
                kwargs={"redemption_id": self.redemption.pk, "decision": "accept"},
            )
        )
        self.assertEqual(response.status_code, 403)
        self.redemption.refresh_from_db()
        self.assertEqual(self.redemption.fulfillment_snapshot["consent_state"], "pending")

    def test_explicit_space_authority_can_accept_benefit(self):
        self.client.force_login(self.actor)
        response = self.client.post(
            reverse(
                "recognition:redemption-decision",
                kwargs={"redemption_id": self.redemption.pk, "decision": "accept"},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.redemption.refresh_from_db()
        self.assertEqual(self.redemption.fulfillment_snapshot["consent_state"], "accepted")
        self.assertEqual(self.redemption.fulfillment_snapshot["consent_actor_profile_id"], str(self.actor.pk))
