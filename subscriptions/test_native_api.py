"""Native Subscription facade: personal authority and financial linkage."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from payments.selectors import obligations_visible_to

from .billing_models import PlanVersionBillingTerms
from .billing_services import create_subscription_billing_obligation
from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    SubscriptionPlanType,
    SubscriptionSubjectType,
    SubscriptionTransitionKind,
)
from .models import PlanVersion, SubscriptionPlan
from .runtime_models import Subscription
from .security_services import request_subscription_transition_for_actor
from .services import publish_plan_version
from .transition_models import SubscriptionTransition

User = get_user_model()


class NativePersonalSubscriptionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="native-billing-owner", password="test-only")
        self.other = User.objects.create_user(username="native-billing-other", password="test-only")
        self.subscription = Subscription.objects.get(profile=self.owner)
        self.other_subscription = Subscription.objects.get(profile=self.other)
        plan = SubscriptionPlan.objects.create(
            code="native.billing.plan",
            plan_type=SubscriptionPlanType.BASE,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        self.version = PlanVersion.objects.create(
            plan=plan, version=1, name="Formule native",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        )
        publish_plan_version(self.version)
        self.version.refresh_from_db()

    def test_anonymous_denied_and_read_scoped_to_self(self):
        url = reverse("subscriptions_native:me")
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response.json()["subscription"]["id"], str(self.subscription.pk))
        self.assertNotIn(str(self.other_subscription.pk), str(response.json()))

    def test_preview_is_read_only_and_transition_idempotent(self):
        self.client.force_login(self.owner)
        url = reverse("subscriptions_native:plan", args=[self.version.pk])
        original = SubscriptionTransition.objects.filter(subscription=self.subscription).count()
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(SubscriptionTransition.objects.filter(subscription=self.subscription).count(), original)
        data = {"idempotency_key": "native-billing-stable-intent"}
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertEqual(
            SubscriptionTransition.objects.filter(
                subscription=self.subscription, idempotency_key=data["idempotency_key"]
            ).count(), 1
        )

    def test_change_requires_confirmation_reference(self):
        self.client.force_login(self.owner)
        url = reverse("subscriptions_native:plan", args=[self.version.pk])
        self.assertEqual(self.client.post(url, {}).status_code, 400)
        self.assertFalse(SubscriptionTransition.objects.filter(subscription=self.subscription).exists())

    def test_other_subject_plan_cannot_be_selected(self):
        space_plan = SubscriptionPlan.objects.create(
            code="native.billing.space.plan", plan_type=SubscriptionPlanType.BASE,
            subject_type=SubscriptionSubjectType.SPACE,
        )
        version = PlanVersion.objects.create(
            plan=space_plan, version=1, name="Space only",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        )
        publish_plan_version(version)
        self.client.force_login(self.owner)
        url = reverse("subscriptions_native:plan", args=[version.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"idempotency_key": "native-cross-scope"}).status_code, 404)

    def test_cannot_change_another_person_transition(self):
        transition = request_subscription_transition_for_actor(
            actor=self.other, subscription_id=self.other_subscription.pk,
            kind=SubscriptionTransitionKind.BASE_SWITCH,
            target_plan_version_id=self.version.pk,
            request_origin="self_service", idempotency_key="native-other-intent",
        )
        self.client.force_login(self.owner)
        for action in ("cancel", "complete"):
            url = reverse("subscriptions_native:transition", args=[transition.pk, action])
            self.assertEqual(self.client.post(url).status_code, 404)

    def test_subscription_obligation_visible_to_canonical_payer_only(self):
        terms = PlanVersionBillingTerms.objects.create(
            plan_version=self.version, amount="12.00", currency="USD",
            billing_period_unit="month",
        )
        # actor=None reproduces a server-generated (not user-created) obligation.
        obligation = create_subscription_billing_obligation(
            subscription=self.subscription, billing_terms=terms,
            billing_key="native-auto-obligation", actor=None,
        )
        self.client.force_login(self.owner)
        data = self.client.get(reverse("subscriptions_native:me")).json()
        self.assertIn(str(obligation.pk), [row["id"] for row in data["billing"]["items"]])
        self.assertTrue(obligations_visible_to(self.owner).filter(pk=obligation.pk).exists())
        self.assertFalse(obligations_visible_to(self.other).filter(pk=obligation.pk).exists())
        self.assertEqual(
            self.client.get(reverse("subscriptions_native:obligations")).status_code, 200
        )
