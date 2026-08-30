from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus

from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    EntitlementAggregationStrategy,
    FeatureEnforcementPolicy,
    FeatureValueType,
    SubscriptionItemStatus,
    SubscriptionPlanType,
    SubscriptionSubjectType,
)
from .entitlements import resolve_effective_entitlements, resolve_entitlement
from .models import (
    EntitlementGrant,
    FeatureDefinition,
    PlanEntitlement,
    PlanVersion,
    Subscription,
    SubscriptionItem,
    SubscriptionPlan,
)
from .runtime_services import (
    SubscriptionBootstrapError,
    SubscriptionStateError,
    add_subscription_item,
    create_entitlement_grant,
    end_subscription_item,
    ensure_subscription_for_profile,
    ensure_subscription_for_space,
    revoke_entitlement_grant,
)
from .selectors import get_current_default_base_plan, resolve_activity_subscription
from .services import publish_plan_version


User = get_user_model()


class S2Mixin:
    @classmethod
    def setUpTestData(cls):
        cls.profile = User.objects.create_user(
            username="s2-profile", email="s2-profile@example.test", password="test-only-password"
        )
        cls.space = Organization.objects.create(name="S2 Space", created_by=cls.profile)

    def feature(self, code, *, value_type=FeatureValueType.BOOLEAN, strategy=EntitlementAggregationStrategy.BOOLEAN_OR, supports_profile=True, supports_space=True, enum_values=None):
        return FeatureDefinition.objects.create(
            code=code,
            name=code,
            domain="test",
            value_type=value_type,
            supports_profile=supports_profile,
            supports_space=supports_space,
            aggregation_strategy=strategy,
            enforcement_policy=FeatureEnforcementPolicy.FEATURE_GATE,
            enum_values=enum_values or [],
        )

    def published_plan(self, code, *, subject_type=SubscriptionSubjectType.SPACE, plan_type=SubscriptionPlanType.ADDON, entitlements=None):
        plan = SubscriptionPlan.objects.create(code=code, plan_type=plan_type, subject_type=subject_type)
        version = PlanVersion.objects.create(
            plan=plan,
            version=1,
            name=code,
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        )
        for feature, value in entitlements or []:
            PlanEntitlement.objects.create(plan_version=version, feature=feature, value=value)
        publish_plan_version(version)
        version.refresh_from_db()
        return plan, version

    def replace_base(self, subscription, version):
        current = subscription.items.get(status=SubscriptionItemStatus.ACTIVE, item_type=SubscriptionPlanType.BASE)
        end_subscription_item(item=current, reason="test base replacement")
        return add_subscription_item(subscription=subscription, plan_version=version)


class SubscriptionBootstrapTests(S2Mixin, TestCase):
    def test_profile_and_space_are_bootstrapped_with_exact_default_base_version(self):
        profile_sub = Subscription.objects.get(profile=self.profile)
        space_sub = Subscription.objects.get(space=self.space)
        profile_default = get_current_default_base_plan(SubscriptionSubjectType.PROFILE)
        space_default = get_current_default_base_plan(SubscriptionSubjectType.SPACE)
        self.assertEqual(profile_sub.items.get(status="active", item_type="base").plan_version_id, profile_default.current_version_id)
        self.assertEqual(space_sub.items.get(status="active", item_type="base").plan_version_id, space_default.current_version_id)

    def test_bootstrap_is_idempotent_and_subject_is_unique(self):
        for _ in range(3):
            ensure_subscription_for_profile(self.profile)
            ensure_subscription_for_space(self.space)
        self.assertEqual(Subscription.objects.filter(profile=self.profile).count(), 1)
        self.assertEqual(Subscription.objects.filter(space=self.space).count(), 1)
        self.assertEqual(SubscriptionItem.objects.filter(subscription__profile=self.profile, status="active", item_type="base").count(), 1)
        self.assertEqual(SubscriptionItem.objects.filter(subscription__space=self.space, status="active", item_type="base").count(), 1)

    def test_subscription_subject_xor_and_uniqueness_are_enforced(self):
        with self.assertRaises(ValidationError):
            Subscription.objects.create()
        with self.assertRaises(ValidationError):
            Subscription.objects.create(profile=self.profile, space=self.space)
        with self.assertRaises((ValidationError, IntegrityError)):
            with transaction.atomic():
                Subscription.objects.create(profile=self.profile)

    def test_missing_default_is_explicit_for_new_profile(self):
        SubscriptionPlan.objects.filter(subject_type="profile", is_default=True).update(is_default=False)
        with self.assertRaises(SubscriptionBootstrapError):
            with transaction.atomic():
                User.objects.create_user(username="s2-no-base", email="s2-no-base@example.test", password="x")

    def test_publishing_new_default_version_does_not_move_existing_item(self):
        plan = get_current_default_base_plan(SubscriptionSubjectType.PROFILE)
        pinned = Subscription.objects.get(profile=self.profile).items.get(status="active", item_type="base")
        old_version_id = pinned.plan_version_id
        v2 = PlanVersion.objects.create(plan=plan, version=2, name="Profile Base v2")
        activities = FeatureDefinition.objects.get(code="activities.create")
        PlanEntitlement.objects.create(plan_version=v2, feature=activities, value=True)
        publish_plan_version(v2)
        pinned.refresh_from_db()
        self.assertEqual(pinned.plan_version_id, old_version_id)
        self.assertNotEqual(plan.current_version_id, pinned.plan_version_id)


class SubscriptionItemTests(S2Mixin, TestCase):
    def test_addons_support_multiple_plans_but_refuse_duplicate_active_plan(self):
        subscription = Subscription.objects.get(space=self.space)
        _, v1 = self.published_plan("s2.addon.one")
        _, v2 = self.published_plan("s2.addon.two")
        add_subscription_item(subscription=subscription, plan_version=v1)
        add_subscription_item(subscription=subscription, plan_version=v2)
        self.assertEqual(subscription.items.filter(status="active", item_type="addon").count(), 2)
        with self.assertRaises(SubscriptionStateError):
            add_subscription_item(subscription=subscription, plan_version=v1)

    def test_draft_and_subject_mismatch_are_refused(self):
        subscription = Subscription.objects.get(space=self.space)
        profile_plan = SubscriptionPlan.objects.create(code="s2.profile.addon", plan_type="addon", subject_type="profile")
        profile_version = PlanVersion.objects.create(plan=profile_plan, version=1, name="Profile addon")
        with self.assertRaises(SubscriptionStateError):
            add_subscription_item(subscription=subscription, plan_version=profile_version)
        _, published_profile = self.published_plan("s2.profile.published", subject_type="profile")
        with self.assertRaises(SubscriptionStateError):
            add_subscription_item(subscription=subscription, plan_version=published_profile)

    def test_second_active_base_refused_and_ended_history_preserved(self):
        subscription = Subscription.objects.get(space=self.space)
        _, version = self.published_plan("s2.space.base.alt", plan_type="base")
        with self.assertRaises(SubscriptionStateError):
            add_subscription_item(subscription=subscription, plan_version=version)
        old = subscription.items.get(status="active", item_type="base")
        end_subscription_item(item=old, reason="manual test downgrade")
        new = add_subscription_item(subscription=subscription, plan_version=version)
        self.assertTrue(SubscriptionItem.objects.filter(pk=old.pk, status="ended").exists())
        self.assertEqual(new.plan_version_id, version.pk)
        with self.assertRaises(ValidationError):
            old.delete()


class GrantTests(S2Mixin, TestCase):
    def test_grant_xor_subject_type_value_and_revocation_are_strict(self):
        team = FeatureDefinition.objects.get(code="team.members")
        with self.assertRaises(ValidationError):
            create_entitlement_grant(feature=team, value=5, reason="bad subject", profile=self.profile)
        with self.assertRaises(ValidationError):
            create_entitlement_grant(feature=team, value="5", reason="bad value", space=self.space)
        grant = create_entitlement_grant(feature=team, value=5, reason="beta", space=self.space, granted_by=self.profile)
        self.assertEqual(grant.value, 5)
        revoke_entitlement_grant(grant=grant, actor=self.profile, reason="beta ended")
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revoked_at)
        with self.assertRaises(ValidationError):
            grant.delete()

    def test_future_expired_and_revoked_grants_do_not_resolve(self):
        feature = self.feature("s2.grant.boolean", supports_profile=False, supports_space=True)
        now = timezone.now()
        create_entitlement_grant(feature=feature, value=True, reason="future", space=self.space, valid_from=now + timedelta(days=1))
        create_entitlement_grant(feature=feature, value=True, reason="expired", space=self.space, valid_from=now - timedelta(days=2), valid_until=now - timedelta(days=1))
        revoked = create_entitlement_grant(feature=feature, value=True, reason="revoked", space=self.space)
        revoke_entitlement_grant(grant=revoked, reason="done")
        result = resolve_entitlement(self.space, feature.code, at=now)
        self.assertIsNone(result.effective_value)
        self.assertFalse(result.allowed)


class EffectiveEntitlementTests(S2Mixin, TestCase):
    def test_all_aggregation_strategies_and_replace_priority(self):
        boolean = self.feature("s2.agg.bool", supports_profile=False, supports_space=True)
        summed = self.feature("s2.agg.sum", value_type="integer", strategy="SUM", supports_profile=False, supports_space=True)
        maximum = self.feature("s2.agg.max", value_type="integer", strategy="MAX", supports_profile=False, supports_space=True)
        replaced = self.feature("s2.agg.replace", value_type="enum", strategy="REPLACE", supports_profile=False, supports_space=True, enum_values=["base", "addon", "grant"])
        _, base_version = self.published_plan(
            "s2.agg.base", plan_type="base", entitlements=[(boolean, False), (summed, 10), (maximum, 10), (replaced, "base")]
        )
        subscription = Subscription.objects.get(space=self.space)
        self.replace_base(subscription, base_version)
        _, addon_version = self.published_plan(
            "s2.agg.addon", entitlements=[(boolean, True), (summed, 5), (maximum, 25), (replaced, "addon")]
        )
        add_subscription_item(subscription=subscription, plan_version=addon_version)
        create_entitlement_grant(feature=summed, value=5, reason="sum grant", space=self.space)
        create_entitlement_grant(feature=replaced, value="grant", reason="replace grant", space=self.space)

        results = resolve_effective_entitlements(self.space)
        self.assertIs(results[boolean.code].effective_value, True)
        self.assertEqual(results[summed.code].effective_value, 20)
        self.assertEqual(results[maximum.code].effective_value, 25)
        self.assertEqual(results[replaced.code].effective_value, "grant")
        self.assertEqual([source.source_type for source in results[replaced.code].sources], ["base", "addon", "grant"])

    def test_team_members_usage_uses_organization_domain_and_preserves_over_limit(self):
        team_feature = FeatureDefinition.objects.get(code="team.members")
        _, base_version = self.published_plan("s2.team.base", plan_type="base", entitlements=[(team_feature, 10)])
        subscription = Subscription.objects.get(space=self.space)
        self.replace_base(subscription, base_version)
        team = Team.objects.create(organization=self.space, name="Core", is_default=True)

        for index in range(4):
            user = User.objects.create_user(username=f"s2-member-{index}", email=f"s2-member-{index}@example.test", password="x")
            TeamMembership.objects.create(team=team, user=user, status=TeamMembershipStatus.ACTIVE)
        result = resolve_entitlement(self.space, "team.members")
        self.assertEqual((result.usage, result.remaining, result.allowed, result.over_limit), (4, 6, True, False))

        for index in range(4, 10):
            user = User.objects.create_user(username=f"s2-member-{index}", email=f"s2-member-{index}@example.test", password="x")
            TeamMembership.objects.create(team=team, user=user, status=TeamMembershipStatus.ACTIVE)
        result = resolve_entitlement(self.space, "team.members")
        self.assertEqual((result.usage, result.remaining, result.allowed, result.reason_code), (10, 0, False, "limit_reached"))

        extra = User.objects.create_user(username="s2-member-over", email="s2-member-over@example.test", password="x")
        TeamMembership.objects.create(team=team, user=extra, status=TeamMembershipStatus.ACTIVE)
        result = resolve_entitlement(self.space, "team.members")
        self.assertEqual(result.usage, 11)
        self.assertEqual(result.remaining, 0)
        self.assertFalse(result.allowed)
        self.assertTrue(result.over_limit)
        self.assertEqual(result.reason_code, "over_limit")
        self.assertEqual(TeamMembership.objects.filter(team=team, status="active").count(), 11)

    def test_space_only_feature_is_not_resolved_for_profile(self):
        with self.assertRaises(ValidationError):
            resolve_entitlement(self.profile, "team.members")


class ActivitySubscriptionTests(S2Mixin, TestCase):
    def test_personal_activity_uses_profile_subscription(self):
        activity = Activity.objects.create(owner_profile=self.profile, created_by=self.profile, title="Personal S2")
        self.assertEqual(resolve_activity_subscription(activity).profile_id, self.profile.pk)

    def test_space_activity_uses_space_subscription_not_collaborator_profile(self):
        collaborator = User.objects.create_user(username="s2-collab", email="s2-collab@example.test", password="x")
        activity = Activity.objects.create(space=self.space, created_by=collaborator, title="Space S2")
        resolved = resolve_activity_subscription(activity)
        self.assertEqual(resolved.space_id, self.space.pk)
        self.assertNotEqual(resolved.profile_id, collaborator.pk)
