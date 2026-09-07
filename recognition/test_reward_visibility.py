import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from organizations.models import Organization

from .models import RewardDefinition, RewardKind
from .selectors import active_rewards
from .services import get_or_create_account


class RecognitionRewardVisibilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.profile = User.objects.create_user(
            username="recognition-reward-visibility-profile",
            email="recognition-reward-visibility@example.test",
            password="test-pass-2026",
        )
        self.space = Organization.objects.create(
            name="Recognition Reward Visibility Space",
            created_by=self.profile,
        )

    def _fund(self, *, profile=None, space=None):
        account = get_or_create_account(profile=profile, space=space)
        account.points_balance = 100
        account.lifetime_earned = 100
        account.save()
        return account

    def test_space_owner_can_see_profile_only_reward_for_another_beneficiary(self):
        reward = RewardDefinition.objects.create(
            code="profile-only-gift",
            version=1,
            name="Profile only gift",
            kind=RewardKind.PROMOTION,
            points_cost=10,
            beneficiary_allowed=True,
            eligibility={"beneficiary_subject_types": ["profile"]},
            fulfillment={"promotion_id": str(uuid.uuid4())},
        )
        account = self._fund(space=self.space)
        visible = active_rewards(owner_account=account)
        self.assertIn(reward, visible)
        rendered = next(item for item in visible if item.pk == reward.pk)
        self.assertFalse(rendered.recognition_self_eligible)
        self.assertTrue(rendered.recognition_requires_other_beneficiary)

    def test_same_profile_only_reward_is_self_eligible_for_profile_owner(self):
        reward = RewardDefinition.objects.create(
            code="profile-self",
            version=1,
            name="Profile self",
            kind=RewardKind.PROMOTION,
            points_cost=10,
            beneficiary_allowed=True,
            eligibility={"beneficiary_subject_types": ["profile"]},
            fulfillment={"promotion_id": str(uuid.uuid4())},
        )
        account = self._fund(profile=self.profile)
        rendered = next(item for item in active_rewards(owner_account=account) if item.pk == reward.pk)
        self.assertTrue(rendered.recognition_self_eligible)
        self.assertFalse(rendered.recognition_requires_other_beneficiary)
