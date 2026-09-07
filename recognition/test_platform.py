from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from organizations.models import Organization

from .achievements import grant_due_achievements
from .economy import redeem_reward
from .ingest import record_signal
from .models import RecognitionAccount, RecognitionPolicy, RecognitionSignal, RewardDefinition
from .runtime import run_default_recognition_cycle
from .selectors import compact_credits
from .services import get_or_create_account


class RecognitionPlatformTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="recognition-owner", email="recognition-owner@example.test", password="test-pass-2026")
        self.other = User.objects.create_user(username="recognition-other", email="recognition-other@example.test", password="test-pass-2026")
        self.space = Organization.objects.create(name="Recognition Space", created_by=self.user)

    def test_default_policy_is_seeded_and_refund_weight_is_half_payment_default(self):
        policy = RecognitionPolicy.objects.get(code="default-network-utility", version=1)
        payment = policy.rules.get(code="payment-succeeded")
        refund = policy.rules.get(code="payment-refunded")
        self.assertEqual(payment.measure["value"], "2")
        self.assertEqual(refund.measure["value"], "1")

    def test_runtime_consumes_semantic_signal_once_and_credits_space(self):
        now = timezone.now()
        record_signal(
            signal_id="test-payment-1",
            signal_kind="payment.succeeded",
            object_type="payment",
            object_id="p-1",
            outcome_identity="payment:p-1:succeeded",
            occurred_at=now - timedelta(hours=1),
            available_at=now - timedelta(hours=1),
            values={"count": 1},
            contributors=[{"subject_type": "space", "subject_id": str(self.space.pk), "causal_mode": "operate", "weight": "1"}],
        )
        first = run_default_recognition_cycle(now=now)
        account = RecognitionAccount.objects.get(space=self.space)
        self.assertEqual(first["issued_points"], 2)
        self.assertEqual(account.points_balance, 2)
        self.assertIsNotNone(RecognitionSignal.objects.get(signal_id="test-payment-1").processed_at)
        second = run_default_recognition_cycle(now=now + timedelta(minutes=1))
        account.refresh_from_db()
        self.assertEqual(second["issued_points"], 0)
        self.assertEqual(account.points_balance, 2)

    def test_reward_can_be_used_for_another_profile_without_transferring_wallet_credits(self):
        owner = get_or_create_account(profile=self.user)
        owner.points_balance = 100
        owner.lifetime_earned = 100
        owner.save()
        reward = RewardDefinition.objects.create(
            code="gift-test", version=1, name="Bénéfice test", points_cost=25,
            beneficiary_allowed=True, fulfillment={"owner_domain": "external"},
        )
        redemption = redeem_reward(owner_account=owner, reward=reward, idempotency_key="gift-test-1", actor_profile=self.user, beneficiary_profile=self.other)
        owner.refresh_from_db()
        self.assertEqual(owner.points_balance, 75)
        self.assertEqual(redemption.beneficiary_profile, self.other)
        self.assertEqual(redemption.fulfillment_snapshot["delegated_domain"], "external")
        self.assertFalse(RecognitionAccount.objects.filter(profile=self.other).exists())

    def test_private_profile_dashboard_requires_login_and_space_requires_authority(self):
        response = self.client.get(reverse("recognition:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(reverse("recognition:space-dashboard", kwargs={"space_id": self.space.pk}))
        self.assertEqual(response.status_code, 403)

    def test_achievement_is_separate_from_credit_balance(self):
        account = get_or_create_account(profile=self.user)
        account.points_balance = 1
        account.lifetime_earned = 1
        account.save()
        grants = grant_due_achievements(account=account)
        self.assertTrue(any(grant.achievement.code == "first-value-created" for grant in grants))
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 1)

    def test_compact_credit_display_is_only_presentation(self):
        self.assertEqual(compact_credits(2000), "2k crédits")
        self.assertEqual(compact_credits(63_300_000_000), "63,3G crédits")

    def test_no_credit_field_is_added_to_user_model(self):
        field_names = {field.name for field in get_user_model()._meta.get_fields()}
        self.assertNotIn("points", field_names)
        self.assertNotIn("credits", field_names)
