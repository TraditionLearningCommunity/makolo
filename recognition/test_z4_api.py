from django.test import TestCase

from rest_framework.test import APIClient

from accounts.models import User
from recognition.economy import redeem_reward
from recognition.models import (
    RecognitionAccount,
    RecognitionRedemption,
    RewardDefinition,
    RewardKind,
)
from recognition.services import get_or_create_account


PASSWORD = "Makolo!2026-Z4-RecognitionA7"


class RecognitionZ4APIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="z4-recognition@makolo.test",
            username="z4-recognition",
            password=PASSWORD,
        )
        self.other = User.objects.create_user(
            email="z4-recognition-other@makolo.test",
            username="z4-recognition-other",
            password=PASSWORD,
        )
        self.third = User.objects.create_user(
            email="z4-recognition-third@makolo.test",
            username="z4-recognition-third",
            password=PASSWORD,
        )
        self.client.force_authenticate(self.user)

    def _account(self, user=None, *, balance=100):
        user = user or self.user
        account = get_or_create_account(profile=user)
        account.points_balance = balance
        account.lifetime_earned = balance
        account.save(
            update_fields=["points_balance", "lifetime_earned", "updated_at"]
        )
        return account

    def _reward(self, *, code="z4-reward", cost=20, consent=False):
        return RewardDefinition.objects.create(
            code=code,
            version=1,
            name=f"Reward {code}",
            kind=RewardKind.OTHER,
            points_cost=cost,
            beneficiary_allowed=True,
            acceptance_required=consent,
            fulfillment={"owner_domain": "z4-test"},
        )

    def test_me_requires_authentication_and_does_not_create_account_on_read(self):
        anonymous = APIClient()
        denied = anonymous.get("/api/v1/recognition/me/")
        self.assertEqual(denied.status_code, 401)

        self.assertFalse(
            RecognitionAccount.objects.filter(profile=self.user).exists()
        )
        response = self.client.get("/api/v1/recognition/me/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["account"])
        self.assertEqual(response.json()["rewards"], [])
        self.assertFalse(
            RecognitionAccount.objects.filter(profile=self.user).exists()
        )

    def test_me_exposes_only_personal_recognition_state_and_safe_reward_fields(self):
        account = self._account(balance=80)
        reward = self._reward(cost=25)

        response = self.client.get("/api/v1/recognition/me/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["account"]["id"], str(account.pk))
        self.assertEqual(payload["account"]["points_balance"], 80)
        self.assertEqual(payload["rewards"][0]["id"], str(reward.pk))
        self.assertEqual(payload["rewards"][0]["points_cost"], 25)
        self.assertEqual(payload["rewards"][0]["capabilities"], ["redeem"])
        serialized = str(payload)
        self.assertNotIn("fulfillment_snapshot", serialized)
        self.assertNotIn("owner_domain", serialized)
        self.assertNotIn(self.other.email, serialized)

    def test_self_redemption_is_idempotent_and_uses_canonical_economy(self):
        account = self._account(balance=100)
        reward = self._reward(cost=20)

        first = self.client.post(
            f"/api/v1/recognition/rewards/{reward.pk}/redeem/",
            {"idempotency_key": "z4-self-redeem-1"},
            format="json",
        )
        second = self.client.post(
            f"/api/v1/recognition/rewards/{reward.pk}/redeem/",
            {"idempotency_key": "z4-self-redeem-1"},
            format="json",
        )

        self.assertEqual(first.status_code, 201, first.json())
        self.assertEqual(second.status_code, 200, second.json())
        self.assertEqual(first.json()["id"], second.json()["id"])
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 80)
        self.assertEqual(
            RecognitionRedemption.objects.filter(owner_account=account).count(),
            1,
        )
        self.assertNotIn("fulfillment_snapshot", first.json())

    def test_foreign_idempotency_key_is_rejected_without_leaking_redemption(self):
        other_account = self._account(self.other, balance=100)
        reward = self._reward(code="z4-other-reward", cost=10)
        foreign = redeem_reward(
            owner_account=other_account,
            reward=reward,
            idempotency_key="z4-shared-key",
            actor_profile=self.other,
            beneficiary_profile=self.other,
        )

        self._account(self.user, balance=100)
        response = self.client.post(
            f"/api/v1/recognition/rewards/{reward.pk}/redeem/",
            {"idempotency_key": "z4-shared-key"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertNotIn(str(foreign.pk), str(response.json()))

    def test_incoming_benefit_decision_is_beneficiary_scoped(self):
        owner_account = self._account(self.other, balance=100)
        reward = self._reward(code="z4-consent", cost=30, consent=True)
        redemption = redeem_reward(
            owner_account=owner_account,
            reward=reward,
            idempotency_key="z4-consent-1",
            actor_profile=self.other,
            beneficiary_profile=self.user,
        )

        inbox = self.client.get("/api/v1/recognition/me/")
        self.assertEqual(inbox.status_code, 200)
        incoming = inbox.json()["incoming"]
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0]["id"], str(redemption.pk))
        self.assertEqual(incoming[0]["capabilities"], ["accept", "decline"])

        third_client = APIClient()
        third_client.force_authenticate(self.third)
        denied = third_client.post(
            f"/api/v1/recognition/redemptions/{redemption.pk}/accept/",
            {},
            format="json",
        )
        self.assertEqual(denied.status_code, 404)

        declined = self.client.post(
            f"/api/v1/recognition/redemptions/{redemption.pk}/decline/",
            {},
            format="json",
        )
        self.assertEqual(declined.status_code, 200, declined.json())
        self.assertEqual(declined.json()["status"], "cancelled")
        owner_account.refresh_from_db()
        self.assertEqual(owner_account.points_balance, 100)

    def test_redeem_requires_explicit_idempotency_key(self):
        self._account(balance=100)
        reward = self._reward(code="z4-key-required", cost=10)

        response = self.client.post(
            f"/api/v1/recognition/rewards/{reward.pk}/redeem/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "idempotency_key",
            response.json()["error"]["fields"],
        )
