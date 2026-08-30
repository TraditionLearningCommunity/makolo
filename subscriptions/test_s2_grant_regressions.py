from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from .contracts import (
    EntitlementAggregationStrategy,
    FeatureEnforcementPolicy,
    FeatureValueType,
    SubscriptionItemStatus,
)
from .models import FeatureDefinition, SubscriptionItem
from .runtime_services import (
    create_entitlement_grant,
    end_subscription_item,
    revoke_entitlement_grant,
)


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


class SubscriptionItemHistoryRegressionTests(TestCase):
    def test_bulk_update_cannot_rewrite_pinned_item(self):
        profile = User.objects.create_user(
            username="item-bulk-history",
            email="item-bulk-history@example.test",
            password="test-only-password",
        )
        item = SubscriptionItem.objects.get(subscription__profile=profile, item_type="base", status="active")

        with self.assertRaises(ValidationError):
            SubscriptionItem.objects.filter(pk=item.pk).update(plan_version=item.plan_version)

    def test_ended_item_cannot_be_reactivated(self):
        profile = User.objects.create_user(
            username="item-ended-history",
            email="item-ended-history@example.test",
            password="test-only-password",
        )
        item = SubscriptionItem.objects.get(subscription__profile=profile, item_type="base", status="active")
        item = end_subscription_item(item=item, reason="Historical regression test")

        item.status = SubscriptionItemStatus.ACTIVE
        item.ends_at = None
        item.ended_reason = ""
        with self.assertRaises(ValidationError):
            item.save()
