from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, Role
from domain_events.contracts import DomainEventType
from organizations.models import Organization, Team, TeamMembership
from requirements.contracts import RequirementAssessmentState, RequirementEvaluationResult, RequirementMode

from .authorization import get_profile_subscription_for_actor, get_space_subscription_for_actor
from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    FeatureEnforcementPolicy,
    FeatureValueType,
    RequirementDisclosure,
    RequirementFailurePolicy,
    RequirementPhase,
    SubscriptionPlanType,
    SubscriptionStatus,
    SubscriptionSubjectType,
)
from .entitlements import resolve_entitlement
from .models import FeatureDefinition, PlanEntitlement, PlanRequirement, PlanVersion, SubscriptionPlan
from .ongoing_services import evaluate_subscription_ongoing_requirements
from .runtime_models import Subscription
from .runtime_services import add_subscription_item
from .services import publish_plan_version


User = get_user_model()


class S5AuthorizationTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(username="s5-actor", email="s5-actor@example.test", password="test-only")
        self.other = User.objects.create_user(username="s5-other", email="s5-other@example.test", password="test-only")
        self.space = Organization.objects.create(name="S5 Space", created_by=self.actor)
        self.other_space = Organization.objects.create(name="S5 Other Space", created_by=self.other)
        self.profile_subscription = Subscription.objects.create(profile=self.actor)
        self.other_profile_subscription = Subscription.objects.create(profile=self.other)
        self.space_subscription = Subscription.objects.create(space=self.space)
        self.other_space_subscription = Subscription.objects.create(space=self.other_space)

    def mandate(self, user, role_code, space=None):
        role = Role.objects.get(code=role_code, is_system=True)
        return Mandate.objects.create(
            profile=user,
            role=role,
            scope_type=role.scope_type,
            space=space if role.scope_type == AuthorityScope.SPACE else None,
        )

    def test_profile_self_authority_is_scoped(self):
        self.assertEqual(get_profile_subscription_for_actor(self.actor, self.profile_subscription.pk), self.profile_subscription)
        with self.assertRaises(Http404):
            get_profile_subscription_for_actor(self.actor, self.other_profile_subscription.pk)

    def test_space_owner_can_manage_but_team_membership_alone_cannot(self):
        self.mandate(self.actor, SystemRoleCode.SPACE_OWNER, self.space)
        self.assertEqual(get_space_subscription_for_actor(self.actor, self.space_subscription.pk, manage=True), self.space_subscription)
        with self.assertRaises(Http404):
            get_space_subscription_for_actor(self.actor, self.other_space_subscription.pk, manage=True)

        member = User.objects.create_user(username="s5-member", email="s5-member@example.test", password="test-only")
        team = Team.objects.create(organization=self.space, name="S5 Team", is_default=True)
        TeamMembership.objects.create(team=team, user=member)
        with self.assertRaises(Http404):
            get_space_subscription_for_actor(member, self.space_subscription.pk, manage=True)

    def test_space_admin_has_view_not_manage_by_default(self):
        self.mandate(self.actor, SystemRoleCode.SPACE_ADMIN, self.space)
        self.assertEqual(get_space_subscription_for_actor(self.actor, self.space_subscription.pk), self.space_subscription)
        with self.assertRaises(Http404):
            get_space_subscription_for_actor(self.actor, self.space_subscription.pk, manage=True)

    def test_permission_contracts_are_seeded(self):
        owner = Role.objects.get(code=SystemRoleCode.SPACE_OWNER, is_system=True)
        admin = Role.objects.get(code=SystemRoleCode.SPACE_ADMIN, is_system=True)
        self.assertTrue(owner.permissions.filter(code=PermissionCode.SPACE_SUBSCRIPTION_MANAGE).exists())
        self.assertTrue(admin.permissions.filter(code=PermissionCode.SPACE_SUBSCRIPTION_VIEW).exists())
        self.assertFalse(admin.permissions.filter(code=PermissionCode.SPACE_SUBSCRIPTION_MANAGE).exists())


class S5OngoingRequirementTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(username="s5-profile", email="s5-profile@example.test", password="test-only")
        self.subscription = Subscription.objects.create(profile=self.profile)
        self.plan = SubscriptionPlan.objects.create(
            code="s5.profile.addon",
            plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        self.version = PlanVersion.objects.create(
            plan=self.plan,
            version=1,
            name="S5 Add-on",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        )
        self.requirement = PlanRequirement.objects.create(
            plan_version=self.version,
            key="ongoing.age",
            title="Condition ongoing",
            phase=RequirementPhase.ONGOING,
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="profile.account_age_days",
            config={"operator": ">=", "value": 1},
            failure_policy=RequirementFailurePolicy.GRACE,
            grace_period_days=7,
            disclosure=RequirementDisclosure.GENERIC,
        )
        publish_plan_version(self.version)
        self.version.refresh_from_db()
        add_subscription_item(subscription=self.subscription, plan_version=self.version)

    @patch("subscriptions.ongoing_services.registry.evaluate")
    def test_grace_deadline_is_stable_and_recovery_reactivates(self, evaluate):
        evaluate.return_value = RequirementEvaluationResult(
            state=RequirementAssessmentState.UNSATISFIED,
            reason_code="profile.account_age_days.unsatisfied",
        )
        start = timezone.now()
        first = evaluate_subscription_ongoing_requirements(self.subscription.pk, now=start)
        self.assertEqual(first.status, SubscriptionStatus.GRACE)
        deadline = first.grace_until
        second = evaluate_subscription_ongoing_requirements(self.subscription.pk, now=start + timedelta(days=1))
        self.assertEqual(second.grace_until, deadline)

        evaluate.return_value = RequirementEvaluationResult(
            state=RequirementAssessmentState.SATISFIED,
            reason_code="profile.account_age_days.satisfied",
        )
        recovered = evaluate_subscription_ongoing_requirements(self.subscription.pk, now=start + timedelta(days=2))
        self.assertEqual(recovered.status, SubscriptionStatus.ACTIVE)
        self.assertIsNone(recovered.grace_until)

    def test_suspension_keeps_effective_value_but_blocks_allowed(self):
        feature = FeatureDefinition.objects.create(
            code="s5.feature",
            name="S5 feature",
            domain="subscriptions",
            value_type=FeatureValueType.BOOLEAN,
            supports_profile=True,
            supports_space=False,
            aggregation_strategy="BOOLEAN_OR",
            enforcement_policy=FeatureEnforcementPolicy.FEATURE_GATE,
        )
        # Published PlanVersions are immutable, so use a separate version for this entitlement.
        plan = SubscriptionPlan.objects.create(
            code="s5.entitlement.addon",
            plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        version = PlanVersion.objects.create(plan=plan, version=1, name="Entitlement S5")
        PlanEntitlement.objects.create(plan_version=version, feature=feature, value=True)
        publish_plan_version(version)
        version.refresh_from_db()
        add_subscription_item(subscription=self.subscription, plan_version=version)
        self.subscription.status = SubscriptionStatus.SUSPENDED
        self.subscription.status_reason = "ongoing_requirement_unsatisfied"
        self.subscription.save(update_fields=["status", "status_reason", "updated_at"])
        result = resolve_entitlement(self.profile, feature.code)
        self.assertTrue(result.effective_value)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "subscription_suspended")


class S5DomainEventContractTests(TestCase):
    def test_subscription_event_contracts_are_registered(self):
        self.assertIn(DomainEventType.SUBSCRIPTION_TRANSITION_COMPLETED, DomainEventType.values)
        self.assertIn(DomainEventType.SUBSCRIPTION_REQUIREMENT_CHANGED, DomainEventType.values)
        self.assertIn(DomainEventType.ORGANIZATION_TEAM_MEMBERSHIP_CHANGED, DomainEventType.values)
