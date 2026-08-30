from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from organizations.models import Organization
from requirements.contracts import RequirementMode

from .contracts import (
    RequirementFailurePolicy,
    RequirementPhase,
    SubscriptionPlanType,
    SubscriptionSubjectType,
)
from .models import (
    EntitlementRequirement,
    FeatureDefinition,
    PlanEntitlement,
    PlanRequirement,
    PlanVersion,
    SubscriptionPlan,
)
from .services import publish_plan_version


User = get_user_model()


class S3RequirementValidationTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="s3-validation",
            email="s3-validation@example.test",
            password="test-only-password",
        )
        self.plan = SubscriptionPlan.objects.create(
            code="s3.validation.profile",
            plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        self.version = PlanVersion.objects.create(plan=self.plan, version=1, name="Validation")

    def make_requirement(self, config):
        return PlanRequirement(
            plan_version=self.version,
            key=f"validation.{PlanRequirement.objects.count()}",
            title="Validation",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="profile.account_age_days",
            config=config,
            failure_policy=RequirementFailurePolicy.BLOCK,
        )

    def test_missing_config_value_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_requirement({"operator": ">="}).full_clean()

    def test_wrong_config_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_requirement({"operator": ">=", "value": "10"}).full_clean()

    def test_unknown_config_key_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_requirement({"operator": ">=", "value": 10, "extra": True}).full_clean()


class S3EntitlementRequirementImmutabilityTests(TestCase):
    def test_published_entitlement_requirement_cannot_be_changed_deleted_or_added(self):
        owner = User.objects.create_user(
            username="s3-ent-immutable",
            email="s3-ent-immutable@example.test",
            password="test-only-password",
        )
        space = Organization.objects.create(name="S3 immutable Space", created_by=owner)
        feature = FeatureDefinition.objects.get(code="custom_roles")
        plan = SubscriptionPlan.objects.create(
            code="s3.entitlement.immutable",
            plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.SPACE,
        )
        version = PlanVersion.objects.create(plan=plan, version=1, name="Immutable Entitlement Requirement")
        entitlement = PlanEntitlement.objects.create(plan_version=version, feature=feature, value=True)
        requirement = EntitlementRequirement.objects.create(
            plan_entitlement=entitlement,
            key="member.count",
            title="Member count",
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="space.member_count",
            config={"operator": ">=", "value": 0},
        )
        publish_plan_version(version)

        requirement.title = "Changed"
        with self.assertRaises(ValidationError):
            requirement.save()
        with self.assertRaises(ValidationError):
            EntitlementRequirement.objects.filter(pk=requirement.pk).update(title="Bulk")
        with self.assertRaises(ValidationError):
            requirement.delete()
        with self.assertRaises(ValidationError):
            EntitlementRequirement.objects.create(
                plan_entitlement=entitlement,
                key="late",
                title="Late",
                mode=RequirementMode.REVIEW,
            )
