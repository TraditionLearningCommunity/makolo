"""Security and end-to-end API tests for financed Subscription coverage."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .billing_models import BillingPeriodUnit, PlanVersionBillingTerms
from .contracts import (
    EntitlementAggregationStrategy, FeatureEnforcementPolicy, FeatureValueType,
    SubscriptionPlanType, SubscriptionSubjectType,
)
from .coverage_models import SubscriptionCoverage
from .entitlements import resolve_entitlement
from .models import FeatureDefinition, PlanEntitlement, PlanVersion, SubscriptionPlan
from .services import publish_plan_version

User = get_user_model()


class CoverageNativeAPITests(TestCase):
    def setUp(self):
        self.payer = User.objects.create_superuser(
            username="coverage-api-payer", email="payer@example.test", password="test-only"
        )
        self.recipient = User.objects.create_user(
            username="coverage-api-recipient", email="recipient@example.test", password="test-only"
        )
        self.other = User.objects.create_user(
            username="coverage-api-other", email="other@example.test", password="test-only"
        )
        self.feature = FeatureDefinition.objects.create(
            code="coverage.api.feature", name="Test funded feature", domain="test",
            value_type=FeatureValueType.BOOLEAN, supports_profile=True, supports_space=True,
            aggregation_strategy=EntitlementAggregationStrategy.BOOLEAN_OR,
            enforcement_policy=FeatureEnforcementPolicy.FEATURE_GATE,
        )
        plan = SubscriptionPlan.objects.create(
            code="coverage.api.plan", plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        self.version = PlanVersion.objects.create(plan=plan, version=1, name="Test funding")
        PlanEntitlement.objects.create(
            plan_version=self.version, feature=self.feature, value=True,
        )
        PlanVersionBillingTerms.objects.create(
            plan_version=self.version, amount="0.00", currency="USD",
            billing_period_unit=BillingPeriodUnit.MONTH, billing_period_count=1,
            coverage_enabled=True, coverage_pricing_mode="flat", coverage_max_quantity=1,
        )
        publish_plan_version(self.version)
        self.version.refresh_from_db()

    def test_paid_by_another_profile_without_receiving_beneficiary_privileges(self):
        self.client.force_login(self.payer)
        url = reverse("subscriptions_native:me-coverages")
        payload = {
            "plan_version_id": str(self.version.pk), "quantity": "1",
            "idempotency_key": "unique-native-coverage-2026",
        }
        bought = self.client.post(url, payload)
        self.assertEqual(bought.status_code, 200, bought.content)
        self.assertEqual(bought["Cache-Control"], "private, no-store")
        second = self.client.post(url, payload)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(bought.json()["id"], second.json()["id"])
        self.assertEqual(SubscriptionCoverage.objects.count(), 1)
        coverage_id = bought.json()["id"]
        allocation_url = reverse("subscriptions_native:funded-coverage-allocations", args=[coverage_id])
        invitation = self.client.post(allocation_url, {
            "profile_id": str(self.recipient.pk),
            "idempotency_key": "unique-coverage-invite",
        })
        self.assertEqual(invitation.status_code, 200, invitation.content)
        allocation_id = invitation.json()["id"]

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(
            reverse("subscriptions_native:funded-coverage", args=[coverage_id])
        ).status_code, 404)
        self.assertEqual(self.client.post(allocation_url, {
            "profile_id": str(self.other.pk),
            "idempotency_key": "forged-invite",
        }).status_code, 404)
        self.assertEqual(self.client.post(
            reverse("subscriptions_native:me-coverage-decision", args=[allocation_id]),
            {"action": "accept"},
        ).status_code, 404)

        self.client.force_login(self.recipient)
        received = self.client.get(url)
        self.assertEqual(received.status_code, 200)
        self.assertEqual(len(received.json()["received"]), 1)
        self.assertEqual(received.json()["funded"], [])
        decision = self.client.post(
            reverse("subscriptions_native:me-coverage-decision", args=[allocation_id]),
            {"action": "accept"},
        )
        self.assertEqual(decision.status_code, 200, decision.content)
        self.assertTrue(resolve_entitlement(self.recipient, self.feature.code).allowed)
        self.assertIsNone(resolve_entitlement(self.payer, self.feature.code).effective_value)

    def test_without_session_no_funding_or_decision(self):
        self.assertIn(
            self.client.get(reverse("subscriptions_native:me-coverages")).status_code,
            (401, 403),
        )
        self.assertIn(
            self.client.post(reverse("subscriptions_native:me-coverages"), {
                "plan_version_id": str(self.version.pk), "quantity": "1",
                "idempotency_key": "forged-purchase",
            }).status_code,
            (401, 403),
        )
        self.assertEqual(SubscriptionCoverage.objects.count(), 0)
