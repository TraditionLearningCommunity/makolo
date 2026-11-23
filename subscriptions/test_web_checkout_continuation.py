"""Web self-service follows the canonical Subscription -> Payments handoff."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from payments.obligation_services import satisfy_payment_obligation

from .billing_models import BillingPeriodUnit, PlanVersionBillingTerms, SubscriptionBillingObligation
from .contracts import AcquisitionMode, CatalogVisibility, SubscriptionPlanType, SubscriptionSubjectType
from .models import PlanVersion, SubscriptionPlan
from .runtime_models import Subscription
from .services import publish_plan_version
from .transition_models import SubscriptionTransition

User = get_user_model()


class WebSubscriptionCheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="web-checkout", password="test-only")
        self.subscription = Subscription.objects.get(profile=self.user)
        self.client.force_login(self.user)

    def test_paid_choice_redirects_to_exact_payment_and_applies_after_settlement(self):
        plan = SubscriptionPlan.objects.create(
            code="checkout.web.paid", subject_type=SubscriptionSubjectType.PROFILE,
            plan_type=SubscriptionPlanType.ADDON,
        )
        version = PlanVersion.objects.create(
            plan=plan, version=1, name="Option Web",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        )
        PlanVersionBillingTerms.objects.create(
            plan_version=version, amount=Decimal("18.00"), currency="USD",
            billing_period_unit=BillingPeriodUnit.MONTH, billing_period_count=1,
        )
        publish_plan_version(version)
        url = reverse("subscriptions:change", args=[version.pk])
        response = self.client.post(url, {"idempotency_key": "checkout-web-paid-intent"})
        self.assertEqual(response.status_code, 302)
        transition = SubscriptionTransition.objects.get(subscription=self.subscription)
        linked = SubscriptionBillingObligation.objects.get(transition=transition)
        self.assertEqual(
            response["Location"],
            reverse("payments:obligation-start", kwargs={"obligation_pk": linked.obligation_id}),
        )
        self.assertFalse(self.subscription.items.filter(plan_version=version, status="active").exists())
        overview = self.client.get(reverse("subscriptions:home"))
        self.assertEqual(overview.status_code, 200)
        self.assertContains(overview, "Reprendre le paiement")
        self.assertNotContains(overview, "Annuler la demande")

        satisfy_payment_obligation(obligation=linked.obligation, source="web-checkout-test")
        transition.refresh_from_db()
        self.assertEqual(transition.status, "completed")
        self.assertTrue(self.subscription.items.filter(plan_version=version, status="active").exists())
