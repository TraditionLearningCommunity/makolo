"""Funded coverage native API: authorization, consent and minimal disclosure."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from organizations.models import Organization

from .billing_models import BillingPeriodUnit, PlanVersionBillingTerms
from .contracts import SubscriptionPlanType, SubscriptionSubjectType
from .coverage_models import coverage_period_end
from .models import PlanVersion, SubscriptionPlan
from .services import publish_plan_version

User = get_user_model()


class CoverageNativeAPITests(TestCase):
    def setUp(self):
        self.payer = User.objects.create_user(username="coverage-api-payer", password="x")
        self.payer.is_superuser = True
        self.payer.save(update_fields=["is_superuser"])
        self.beneficiary = User.objects.create_user(username="coverage-api-beneficiary", password="x")
        self.other = User.objects.create_user(username="coverage-api-outsider", password="x")
        plan = SubscriptionPlan.objects.create(
            code="coverage.api.plan", plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        self.version = PlanVersion.objects.create(plan=plan, version=1, name="Offre test")
        PlanVersionBillingTerms.objects.create(
            plan_version=self.version, amount=Decimal("0.00"),
            currency="USD", billing_period_unit=BillingPeriodUnit.MONTH,
            billing_period_count=1, coverage_enabled=True,
            coverage_pricing_mode="per_seat", coverage_max_quantity=2,
        )
        publish_plan_version(self.version)
        self.starts_at = timezone.now() - timedelta(seconds=5)
        self.ends_at = coverage_period_end(self.starts_at, "month", 1)
        self.collection = reverse("subscriptions_native:personal-coverages")

    def _purchase(self):
        self.client.force_login(self.payer)
        result = self.client.post(
            self.collection, {
                "plan_version_id": str(self.version.pk),
                "quantity": 1,
                "starts_at": self.starts_at.isoformat(),
                "ends_at": self.ends_at.isoformat(),
                "idempotency_key": "test-native-coverage-0001",
            },
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200, result.content)
        return result.json()["id"]

    def test_authentication_private_cache_and_non_disclosure(self):
        anonymous = self.client.get(self.collection)
        self.assertIn(anonymous.status_code, (401, 403))
        coverage_id = self._purchase()
        result = self.client.get(self.collection)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["Cache-Control"], "private, no-store")
        self.assertEqual(result.json()["financed"][0]["id"], coverage_id)
        self.client.force_login(self.other)
        outsider = self.client.get(self.collection)
        self.assertEqual(outsider.status_code, 200)
        self.assertEqual(outsider.json()["financed"], [])
        self.assertEqual(outsider.json()["received"], [])

    def test_payer_can_invite_but_cannot_accept_in_beneficiary_place(self):
        coverage_id = self._purchase()
        invitation_url = reverse(
            "subscriptions_native:personal-coverage-allocate",
            kwargs={"coverage_id": coverage_id},
        )
        response = self.client.post(
            invitation_url, {
                "target_type": "profile",
                "target_id": str(self.beneficiary.pk),
                "idempotency_key": "test-invite-coverage-0001",
            }, content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        allocation_id = response.json()["id"]
        action_url = reverse(
            "subscriptions_native:personal-benefit-decision",
            kwargs={"allocation_id": allocation_id, "operation": "accept"},
        )
        self.assertEqual(self.client.post(action_url, {}, content_type="application/json").status_code, 404)
        self.client.force_login(self.beneficiary)
        received = self.client.get(self.collection).json()
        self.assertEqual(len(received["received"]), 1)
        self.assertNotIn("payer_profile_id", str(received["received"]))
        accepted = self.client.post(action_url, {}, content_type="application/json")
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertEqual(accepted.json()["status"], "active")

    def test_funding_cannot_use_arbitrary_cycle_or_cross_payer(self):
        self.client.force_login(self.payer)
        invalid = self.client.post(
            self.collection, {
                "plan_version_id": str(self.version.pk), "quantity": 1,
                "starts_at": self.starts_at.isoformat(),
                "ends_at": (self.ends_at + timedelta(days=2)).isoformat(),
                "idempotency_key": "invalid-cycle-0001",
            }, content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 400)
        coverage_id = self._purchase()
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("subscriptions_native:personal-coverage-allocate", kwargs={"coverage_id": coverage_id}),
            {"target_type": "profile", "target_id": str(self.other.pk), "idempotency_key": "unauthorized-invite"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_space_coverage_needs_space_manage_authority(self):
        space = Organization.objects.create(name="Coverage protected space", created_by=self.payer)
        url = reverse("subscriptions_native:space-coverages", kwargs={"slug": space.slug})
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {}, content_type="application/json").status_code, 403)
