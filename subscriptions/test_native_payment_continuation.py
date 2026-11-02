"""A choice in self-service continues to payment, not to manual approval."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from payments.obligation_services import satisfy_payment_obligation
from subscriptions.billing_models import BillingPeriodUnit, PlanVersionBillingTerms, SubscriptionBillingObligation
from subscriptions.billing_services import create_subscription_billing_obligation
from subscriptions.contracts import (
    AcquisitionMode, CatalogVisibility, SubscriptionPlanType,
    SubscriptionSubjectType, SubscriptionTransitionStatus,
)
from subscriptions.models import PlanVersion, SubscriptionPlan
from subscriptions.runtime_models import Subscription
from subscriptions.services import publish_plan_version
from subscriptions.transition_models import SubscriptionTransition
from subscriptions.transition_services import cancel_subscription_transition


User = get_user_model()


class NativeSubscriptionPaymentContinuationTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="payment-continuation", email="payment-continuation@example.test",
            password="test-only",
        )
        self.subscription = Subscription.objects.get(profile=self.profile)
        self.client.force_login(self.profile)

    def plan(self, code, *, paid):
        plan = SubscriptionPlan.objects.create(
            code=code, subject_type=SubscriptionSubjectType.PROFILE,
            plan_type=SubscriptionPlanType.ADDON,
        )
        version = PlanVersion.objects.create(
            plan=plan, version=1, name="Option de continuation",
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
            catalog_visibility=CatalogVisibility.PUBLIC,
        )
        if paid:
            PlanVersionBillingTerms.objects.create(
                plan_version=version, amount=Decimal("18.00"), currency="USD",
                billing_period_unit=BillingPeriodUnit.MONTH, billing_period_count=1,
            )
        publish_plan_version(version)
        return version

    def test_paid_change_is_payable_without_manual_approval_and_replay_is_unique(self):
        version = self.plan("continuation.paid", paid=True)
        url = reverse("subscriptions_native:plan", args=[version.pk])
        key = "continuation-paid-intent-0001"
        first = self.client.post(url, {"idempotency_key": key}, content_type="application/json")
        self.assertEqual(first.status_code, 200)
        payload = first.json()
        transition = payload["transition"]
        self.assertEqual(transition["next_action"], "pay")
        self.assertTrue(transition["payment_obligation_id"])
        self.assertEqual(transition["payment_amount"], "18.00")
        self.assertEqual(transition["payment_currency"], "USD")
        self.assertFalse(self.subscription.items.filter(plan_version=version, status="active").exists())

        replay = self.client.post(url, {"idempotency_key": key}, content_type="application/json")
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["transition"]["id"], transition["id"])
        self.assertEqual(
            SubscriptionTransition.objects.filter(subscription=self.subscription).count(), 1,
        )
        link = SubscriptionBillingObligation.objects.get(transition_id=transition["id"])
        self.assertEqual(str(link.obligation_id), transition["payment_obligation_id"])
        self.assertIn("Option de continuation", link.obligation.label)
        with self.assertRaises(ValidationError):
            cancel_subscription_transition(transition=link.transition, actor=self.profile)
        self.assertEqual(link.transition.billing_obligation_links.count(), 1)

        satisfy_payment_obligation(obligation=link.obligation, source="native-continuation-test")
        recorded = SubscriptionTransition.objects.get(pk=transition["id"])
        self.assertEqual(recorded.status, SubscriptionTransitionStatus.COMPLETED)
        self.assertTrue(self.subscription.items.filter(
            plan_version=version, created_via_transition=recorded, status="active",
        ).exists())
        updated = self.client.get(reverse("subscriptions_native:me")).json()
        self.assertFalse(updated["transition"]["open"])
        self.assertEqual(updated["billing"]["items"][0]["transition_id"], transition["id"])

    def test_open_payment_is_actionable_beyond_first_billing_page(self):
        version = self.plan("continuation.paid.old-bill", paid=True)
        response = self.client.post(
            reverse("subscriptions_native:plan", args=[version.pk]),
            {"idempotency_key": "continuation-old-bill-intent-001"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        first_transition = response.json()["transition"]
        payment_id = first_transition["payment_obligation_id"]
        terms = version.billing_terms

        # An unrelated billing history must not hide the pending change.
        for number in range(21):
            create_subscription_billing_obligation(
                subscription=self.subscription, billing_terms=terms,
                billing_key=f"other-history-{number}", actor=None,
            )

        snapshot = self.client.get(reverse("subscriptions_native:me")).json()
        self.assertNotIn(payment_id, [row["id"] for row in snapshot["billing"]["items"]])
        self.assertIsNotNone(snapshot["billing"]["next_offset"])
        transition = snapshot["transition"]
        self.assertEqual(transition["id"], first_transition["id"])
        self.assertEqual(transition["next_action"], "pay")
        self.assertEqual(transition["payment_obligation_id"], payment_id)
        self.assertEqual(transition["payment_amount"], "18.00")
        self.assertFalse(transition["can_cancel"])

    def test_free_change_activates_immediately_without_payment_obligation(self):
        version = self.plan("continuation.free", paid=False)
        url = reverse("subscriptions_native:plan", args=[version.pk])
        response = self.client.post(
            url, {"idempotency_key": "continuation-free-intent-001"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["transition"]["status"], SubscriptionTransitionStatus.COMPLETED)
        self.assertTrue(self.subscription.items.filter(plan_version=version, status="active").exists())
        self.assertFalse(SubscriptionBillingObligation.objects.filter(subscription=self.subscription).exists())
