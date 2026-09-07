from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from .achievements import grant_due_achievements
from .admin import _next_policy_boundary
from .economy import redeem_reward
from .models import (
    AchievementDefinition,
    PolicyStatus,
    RecognitionPolicy,
    RecognitionRule,
    RewardDefinition,
)
from .selectors import active_rewards
from .services import ensure_cursor, get_or_create_account


class RecognitionStaffConfigurationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="recognition-staff-config-owner",
            email="recognition-staff-config@example.test",
            password="Recognition-2026!",
        )
        self.account = get_or_create_account(profile=self.user)
        self.account.points_balance = 100
        self.account.lifetime_earned = 100
        self.account.save()

    def test_published_policy_cannot_gain_a_new_rule(self):
        policy = RecognitionPolicy.objects.create(
            code="published-lock",
            version=1,
            name="Published lock",
            status=PolicyStatus.ACTIVE,
        )
        with self.assertRaises(ValidationError):
            RecognitionRule.objects.create(
                policy=policy,
                code="late-rule",
                name="Late rule",
                signal_kind="access.used",
                channel="real_action",
                measure={"op": "const", "value": 1},
                aggregation="SUM_DISTINCT_OUTCOME",
                outcome_identity={"source": "signal.outcome_identity"},
            )

    def test_policy_publish_time_snaps_forward_to_window_boundary(self):
        start = timezone.now().replace(microsecond=0)
        cursor = ensure_cursor(
            key="staff-boundary-test",
            policy_version="default:v1",
            window_size_hours=24,
            start_at=start,
        )
        target = start + timedelta(hours=25)
        self.assertEqual(
            _next_policy_boundary(cursor=cursor, target=target),
            start + timedelta(hours=48),
        )

    def test_used_reward_is_immutable_and_new_version_is_visible(self):
        reward_v1 = RewardDefinition.objects.create(
            code="staff-versioned-reward",
            version=1,
            name="Reward v1",
            points_cost=10,
            fulfillment={"owner_domain": "external"},
        )
        redeem_reward(
            owner_account=self.account,
            reward=reward_v1,
            idempotency_key="staff-versioned-reward-use",
            actor_profile=self.user,
            beneficiary_profile=self.user,
        )
        reward_v1.points_cost = 11
        with self.assertRaises(ValidationError):
            reward_v1.save()

        reward_v2 = RewardDefinition.objects.create(
            code="staff-versioned-reward",
            version=2,
            name="Reward v2",
            points_cost=12,
            fulfillment={"owner_domain": "external"},
        )
        visible = active_rewards(owner_account=self.account)
        self.assertIn(reward_v2, visible)
        self.assertNotIn(reward_v1, visible)

    def test_granted_achievement_cannot_be_reinterpreted(self):
        achievement = AchievementDefinition.objects.create(
            code="staff-achievement-lock",
            name="Achievement original",
            criteria={"lifetime_earned_gte": 1},
            badge_label="Original",
        )
        grants = grant_due_achievements(account=self.account)
        self.assertTrue(any(grant.achievement_id == achievement.pk for grant in grants))

        achievement.criteria = {"lifetime_earned_gte": 999999}
        with self.assertRaises(ValidationError):
            achievement.save()
        # The FK PROTECT is the strongest source-level guarantee: historical grants keep their definition.
        with self.assertRaises(ProtectedError):
            achievement.delete()
