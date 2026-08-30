from django.contrib.auth import get_user_model
from django.test import TestCase

from .contracts import (
    EntitlementAggregationStrategy,
    FeatureEnforcementPolicy,
    FeatureValueType,
)
from .models import FeatureDefinition
from .runtime_services import create_entitlement_grant, revoke_entitlement_grant


User = get_user_model()


class EntitlementGrantLifecycleRegressionTests(TestCase):
    def test_existing_grant_remains_revocable_after_feature_deactivation(self):
        profile = User.objects.create_user(
            username="grant-revocation-profile",
            email="grant-revocation-profile@example.test",
            password="test-only-password",
        )
        feature = FeatureDefinition.objects.create(
            code="test.revocable_after_deactivation",
            name="Revocable after deactivation",
            domain="test",
            value_type=FeatureValueType.BOOLEAN,
            supports_profile=True,
            aggregation_strategy=EntitlementAggregationStrategy.BOOLEAN_OR,
            enforcement_policy=FeatureEnforcementPolicy.FEATURE_GATE,
        )
        grant = create_entitlement_grant(
            profile=profile,
            feature=feature,
            value=True,
            reason="Regression test",
        )

        feature.is_active = False
        feature.save(update_fields=["is_active", "updated_at"])

        revoked = revoke_entitlement_grant(
            grant=grant,
            actor=profile,
            reason="Feature retired",
        )

        self.assertIsNotNone(revoked.revoked_at)
        self.assertEqual(revoked.revoked_by_id, profile.pk)
        self.assertEqual(revoked.revocation_reason, "Feature retired")
