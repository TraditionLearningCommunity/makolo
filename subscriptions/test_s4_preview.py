from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus

from .contracts import (
    EntitlementAggregationStrategy,
    FeatureEnforcementPolicy,
    FeatureValueType,
    SubscriptionPlanType,
    SubscriptionSubjectType,
    SubscriptionTransitionKind,
)
from .entitlements import resolve_effective_entitlements
from .models import FeatureDefinition, PlanEntitlement, PlanVersion, SubscriptionPlan
from .runtime_models import Subscription, SubscriptionItem
from .runtime_services import add_subscription_item, end_subscription_item
from .services import publish_plan_version
from .transition_models import SubscriptionRequirementAssessment, SubscriptionTransition
from .transition_preview import preview_subscription_change
from .transition_services import complete_subscription_transition, request_subscription_transition


User = get_user_model()


class S4PreviewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="s4-preview-owner",
            email="s4-preview-owner@example.test",
            password="x",
        )
        self.space = Organization.objects.create(
            name="S4 Preview Space",
            created_by=self.owner,
        )
        self.subscription = Subscription.objects.get(space=self.space)
        self.team = Team.objects.create(
            organization=self.space,
            name="S4 Preview Team",
            is_default=True,
        )

    def feature(self, code):
        return FeatureDefinition.objects.create(
            code=code,
            name=code,
            domain="s4-preview",
            value_type=FeatureValueType.BOOLEAN,
            supports_profile=False,
            supports_space=True,
            aggregation_strategy=EntitlementAggregationStrategy.BOOLEAN_OR,
            enforcement_policy=FeatureEnforcementPolicy.FEATURE_GATE,
        )

    def base_version(self, code, entitlements):
        plan = SubscriptionPlan.objects.create(
            code=code,
            plan_type=SubscriptionPlanType.BASE,
            subject_type=SubscriptionSubjectType.SPACE,
        )
        version = PlanVersion.objects.create(plan=plan, version=1, name=code)
        for feature, value in entitlements:
            PlanEntitlement.objects.create(
                plan_version=version,
                feature=feature,
                value=value,
            )
        publish_plan_version(version)
        version.refresh_from_db()
        return version

    def install_base(self, version):
        current = self.subscription.items.get(status="active", item_type="base")
        end_subscription_item(item=current, reason="S4 preview fixture")
        return add_subscription_item(
            subscription=self.subscription,
            plan_version=version,
        )

    def test_preview_reports_gains_losses_quota_drop_and_is_read_only(self):
        current_only = self.feature("s4.preview.current_only")
        target_only = self.feature("s4.preview.target_only")
        team_members = FeatureDefinition.objects.get(code="team.members")
        current = self.base_version(
            "s4.preview.base.current",
            [
                (current_only, True),
                (target_only, False),
                (team_members, 20),
            ],
        )
        target = self.base_version(
            "s4.preview.base.target",
            [
                (current_only, False),
                (target_only, True),
                (team_members, 10),
            ],
        )
        self.install_base(current)

        for index in range(11):
            member = User.objects.create_user(
                username=f"s4-preview-member-{index}",
                email=f"s4-preview-member-{index}@example.test",
                password="x",
            )
            TeamMembership.objects.create(
                team=self.team,
                user=member,
                status=TeamMembershipStatus.ACTIVE,
            )

        before = (
            SubscriptionTransition.objects.count(),
            SubscriptionRequirementAssessment.objects.count(),
            SubscriptionItem.objects.filter(subscription=self.subscription).count(),
        )
        preview = preview_subscription_change(
            subscription=self.subscription,
            kind=SubscriptionTransitionKind.BASE_SWITCH,
            target_plan_version=target,
        )
        after = (
            SubscriptionTransition.objects.count(),
            SubscriptionRequirementAssessment.objects.count(),
            SubscriptionItem.objects.filter(subscription=self.subscription).count(),
        )

        self.assertEqual(before, after)
        self.assertIn(current_only.code, preview.features_lost)
        self.assertIn(target_only.code, preview.features_gained)
        quota = next(
            item for item in preview.quota_changes if item.feature_code == "team.members"
        )
        self.assertEqual(quota.current_value, 20)
        self.assertEqual(quota.target_value, 10)
        self.assertEqual(quota.usage, 11)
        self.assertTrue(quota.over_limit_after_change)
        self.assertIn("over_limit_after_change:team.members", preview.warnings)
        self.assertEqual(
            TeamMembership.objects.filter(
                team=self.team,
                status=TeamMembershipStatus.ACTIVE,
            ).count(),
            11,
        )

    def test_completion_immediately_refreshes_effective_entitlements(self):
        old_feature = self.feature("s4.complete.old_feature")
        new_feature = self.feature("s4.complete.new_feature")
        current = self.base_version(
            "s4.complete.base.current",
            [(old_feature, True), (new_feature, False)],
        )
        target = self.base_version(
            "s4.complete.base.target",
            [(old_feature, False), (new_feature, True)],
        )
        self.install_base(current)
        before = resolve_effective_entitlements(self.space)
        self.assertTrue(before[old_feature.code].allowed)
        self.assertFalse(before[new_feature.code].allowed)

        transition = request_subscription_transition(
            subscription=self.subscription,
            kind=SubscriptionTransitionKind.BASE_SWITCH,
            target_plan_version=target,
            requested_by=self.owner,
            idempotency_key="s4-effective-entitlements",
        )
        complete_subscription_transition(transition=transition)

        after = resolve_effective_entitlements(self.space)
        self.assertFalse(after[old_feature.code].allowed)
        self.assertTrue(after[new_feature.code].allowed)
