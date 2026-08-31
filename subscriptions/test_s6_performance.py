from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from requirements.contracts import RequirementMode

from .contracts import (
    FeatureEnforcementPolicy,
    FeatureValueType,
    SubscriptionPlanType,
    SubscriptionSubjectType,
)
from .eligibility_models import EntitlementRequirement
from .entitlements import resolve_effective_entitlements
from .models import FeatureDefinition, PlanEntitlement, PlanVersion, SubscriptionPlan
from .runtime_models import Subscription
from .runtime_services import add_subscription_item
from .services import publish_plan_version


User = get_user_model()


class S6EffectiveEntitlementQueryTests(TestCase):
    def test_multiple_entitlement_requirements_are_batched(self):
        profile = User.objects.create_user(
            username="s6-perf-profile",
            email="s6-perf-profile@example.test",
            password="test-only",
        )
        subscription = Subscription.objects.get(profile=profile)
        plan = SubscriptionPlan.objects.create(
            code="s6.performance.addon",
            plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        version = PlanVersion.objects.create(plan=plan, version=1, name="S6 Performance Add-on")
        expected_codes = []
        for index in range(6):
            feature = FeatureDefinition.objects.create(
                code=f"s6.performance.feature_{index}",
                name=f"Performance feature {index}",
                domain="subscriptions",
                value_type=FeatureValueType.BOOLEAN,
                supports_profile=True,
                supports_space=False,
                aggregation_strategy="BOOLEAN_OR",
                enforcement_policy=FeatureEnforcementPolicy.FEATURE_GATE,
            )
            entitlement = PlanEntitlement.objects.create(
                plan_version=version,
                feature=feature,
                value=True,
            )
            EntitlementRequirement.objects.create(
                plan_entitlement=entitlement,
                key=f"profile.account_age.feature_{index}",
                title=f"Age condition {index}",
                mode=RequirementMode.AUTOMATIC,
                evaluator_key="profile.account_age_days",
                config={"operator": ">=", "value": 0},
            )
            expected_codes.append(feature.code)
        publish_plan_version(version)
        version.refresh_from_db()
        add_subscription_item(subscription=subscription, plan_version=version)

        with CaptureQueriesContext(connection) as queries:
            results = resolve_effective_entitlements(profile)

        self.assertTrue(set(expected_codes).issubset(results))
        self.assertLessEqual(
            len(queries),
            8,
            "Effective Entitlements must batch requirement gates instead of querying once per Feature.",
        )
