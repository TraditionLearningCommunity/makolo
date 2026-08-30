from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from organizations.models import Organization
from payments.models import PaymentObligation
from requirements.contracts import RequirementAssessmentState, RequirementMode

from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    PlanEligibilityStatus,
    RequirementDisclosure,
    RequirementFailurePolicy,
    RequirementPhase,
    SubscriptionPlanType,
    SubscriptionSubjectType,
)
from .eligibility import EligibilityConfigurationError, resolve_plan_eligibility
from .models import (
    EntitlementRequirement,
    FeatureDefinition,
    PlanEntitlement,
    PlanRequirement,
    PlanVersion,
    SubscriptionPlan,
)
from .entitlements import resolve_entitlement
from .runtime_services import add_subscription_item, create_entitlement_grant, ensure_subscription_for_space
from .services import publish_plan_version


User = get_user_model()


class S3EligibilityTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="s3-profile",
            email="s3-profile@example.test",
            password="test-only-password",
        )

    def make_version(self, *, subject_type=SubscriptionSubjectType.PROFILE, visibility=CatalogVisibility.PUBLIC, acquisition=AcquisitionMode.SELF_SERVICE):
        plan = SubscriptionPlan.objects.create(
            code=f"s3.{subject_type}.{SubscriptionPlan.objects.count()}",
            plan_type=SubscriptionPlanType.ADDON,
            subject_type=subject_type,
        )
        return PlanVersion.objects.create(
            plan=plan,
            version=1,
            name="S3 test plan",
            catalog_visibility=visibility,
            acquisition_mode=acquisition,
        )

    def test_no_requirement_is_available(self):
        version = self.make_version()
        publish_plan_version(version)
        result = resolve_plan_eligibility(self.profile, version)
        self.assertEqual(result.status, PlanEligibilityStatus.AVAILABLE)

    def test_block_pending_is_conditionally_available(self):
        version = self.make_version()
        PlanRequirement.objects.create(
            plan_version=version,
            key="action.required",
            title="Action requise",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.ACTION,
            failure_policy=RequirementFailurePolicy.BLOCK,
        )
        publish_plan_version(version)
        result = resolve_plan_eligibility(self.profile, version)
        self.assertEqual(result.status, PlanEligibilityStatus.CONDITIONALLY_AVAILABLE)
        self.assertEqual(result.requirements[0].state, RequirementAssessmentState.PENDING)

    def test_deny_unsatisfied_is_not_eligible(self):
        version = self.make_version()
        PlanRequirement.objects.create(
            plan_version=version,
            key="account.age",
            title="Ancienneté",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="profile.account_age_days",
            config={"operator": ">=", "value": 9999},
            failure_policy=RequirementFailurePolicy.DENY,
        )
        publish_plan_version(version)
        result = resolve_plan_eligibility(self.profile, version)
        self.assertEqual(result.status, PlanEligibilityStatus.NOT_ELIGIBLE)

    def test_optional_requirement_does_not_block(self):
        version = self.make_version()
        PlanRequirement.objects.create(
            plan_version=version,
            key="optional.review",
            title="Optionnel",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.REVIEW,
            failure_policy=RequirementFailurePolicy.DENY,
            is_mandatory=False,
        )
        publish_plan_version(version)
        self.assertEqual(resolve_plan_eligibility(self.profile, version).status, PlanEligibilityStatus.AVAILABLE)

    def test_internal_and_staff_only_are_hidden_from_self_service(self):
        internal = self.make_version(visibility=CatalogVisibility.INTERNAL)
        staff = self.make_version(acquisition=AcquisitionMode.STAFF_ONLY)
        publish_plan_version(internal)
        publish_plan_version(staff)
        self.assertEqual(resolve_plan_eligibility(self.profile, internal).status, PlanEligibilityStatus.HIDDEN)
        self.assertEqual(resolve_plan_eligibility(self.profile, staff).status, PlanEligibilityStatus.HIDDEN)

    def test_internal_disclosure_does_not_leak_evaluator_details(self):
        version = self.make_version()
        PlanRequirement.objects.create(
            plan_version=version,
            key="internal.age",
            title="Secret internal rule",
            description="Do not expose this",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="profile.account_age_days",
            config={"operator": ">=", "value": 9999},
            failure_policy=RequirementFailurePolicy.BLOCK,
            disclosure=RequirementDisclosure.INTERNAL,
        )
        publish_plan_version(version)
        projection = resolve_plan_eligibility(self.profile, version).requirements[0]
        self.assertEqual(projection.reason_code, "requirement.internal")
        self.assertIsNone(projection.title)
        self.assertIsNone(projection.actual_value)
        self.assertIsNone(projection.expected_value)

    def test_invalid_evaluator_config_and_subject_are_catalog_errors(self):
        version = self.make_version()
        requirement = PlanRequirement(
            plan_version=version,
            key="bad.config",
            title="Bad",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="profile.account_age_days",
            config={"operator": "contains", "value": 1},
            failure_policy=RequirementFailurePolicy.BLOCK,
        )
        with self.assertRaises(ValidationError):
            requirement.full_clean()

        mismatch = PlanRequirement(
            plan_version=version,
            key="bad.subject",
            title="Bad subject",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="space.member_count",
            config={"operator": ">=", "value": 1},
            failure_policy=RequirementFailurePolicy.BLOCK,
        )
        with self.assertRaises(ValidationError):
            mismatch.full_clean()

    def test_phase_policy_and_grace_matrix_is_validated(self):
        version = self.make_version()
        requirement = PlanRequirement(
            plan_version=version,
            key="bad.policy",
            title="Bad policy",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.ACTION,
            failure_policy=RequirementFailurePolicy.WARN,
        )
        with self.assertRaises(ValidationError):
            requirement.full_clean()

    def test_published_requirements_are_immutable(self):
        version = self.make_version()
        requirement = PlanRequirement.objects.create(
            plan_version=version,
            key="immutable",
            title="Immutable",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.ACTION,
            failure_policy=RequirementFailurePolicy.BLOCK,
        )
        publish_plan_version(version)
        requirement.title = "Changed"
        with self.assertRaises(ValidationError):
            requirement.save()
        with self.assertRaises(ValidationError):
            PlanRequirement.objects.filter(pk=requirement.pk).update(title="Bulk changed")
        with self.assertRaises(ValidationError):
            requirement.delete()
        with self.assertRaises(ValidationError):
            PlanRequirement.objects.create(
                plan_version=version,
                key="late",
                title="Late",
                phase=RequirementPhase.ACQUISITION,
                mode=RequirementMode.ACTION,
                failure_policy=RequirementFailurePolicy.BLOCK,
            )

    def test_catalog_evaluation_does_not_create_payment(self):
        version = self.make_version()
        PlanRequirement.objects.create(
            plan_version=version,
            key="payment.pending",
            title="Payment later",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.PAYMENT,
            failure_policy=RequirementFailurePolicy.BLOCK,
        )
        publish_plan_version(version)
        before = PaymentObligation.objects.count()
        for _ in range(10):
            resolve_plan_eligibility(self.profile, version)
        self.assertEqual(PaymentObligation.objects.count(), before)


class S3EntitlementRequirementTests(TestCase):
    def test_feature_requirement_preserves_value_but_blocks_use_and_grant_does_not_bypass(self):
        owner = User.objects.create_user(
            username="s3-space-owner",
            email="s3-space-owner@example.test",
            password="test-only-password",
        )
        space = Organization.objects.create(name="S3 Space", created_by=owner)
        subscription = ensure_subscription_for_space(space)
        feature = FeatureDefinition.objects.get(code="custom_roles")
        plan = SubscriptionPlan.objects.create(
            code="s3.custom-roles-addon",
            plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.SPACE,
        )
        version = PlanVersion.objects.create(plan=plan, version=1, name="Custom roles test")
        entitlement = PlanEntitlement.objects.create(plan_version=version, feature=feature, value=True)
        EntitlementRequirement.objects.create(
            plan_entitlement=entitlement,
            key="space.members.threshold",
            title="Member threshold",
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="space.member_count",
            config={"operator": ">=", "value": 9999},
        )
        publish_plan_version(version)
        add_subscription_item(subscription=subscription, plan_version=version)

        result = resolve_entitlement(space, "custom_roles")
        self.assertTrue(result.effective_value)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "requirement_unsatisfied")

        create_entitlement_grant(feature=feature, value=True, reason="S3 no-bypass test", space=space, granted_by=owner)
        result = resolve_entitlement(space, "custom_roles")
        self.assertTrue(result.effective_value)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "requirement_unsatisfied")
