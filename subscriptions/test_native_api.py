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
from .runtime_models import Subscription, SubscriptionItem
from .runtime_services import add_subscription_item
from .billing_presentation import personal_billing_obligations
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

    def test_completed_addon_removal_replays_same_intent(self):
        addon = SubscriptionPlan.objects.create(
            code="native.billing.addon", plan_type=SubscriptionPlanType.ADDON,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        version = PlanVersion.objects.create(
            plan=addon, version=1, name="Option personnelle",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        )
        publish_plan_version(version)
        item = add_subscription_item(subscription=self.subscription, plan_version=version)
        url = reverse("subscriptions_native:addon-remove", args=[item.pk])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)
        key = {"idempotency_key": "native-remove-addon-intent"}
        response = self.client.post(url, key)
        self.assertEqual(response.status_code, 200)
        transition = SubscriptionTransition.objects.get(
            subscription=self.subscription, idempotency_key=key["idempotency_key"]
        )
        self.assertEqual(transition.status, "ready")
        completed = self.client.post(
            reverse("subscriptions_native:transition", args=[transition.pk, "complete"])
        )
        self.assertEqual(completed.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, "ended")
        self.assertEqual(self.client.post(url, key).status_code, 200)
        self.assertEqual(
            SubscriptionTransition.objects.filter(
                subscription=self.subscription, idempotency_key=key["idempotency_key"]
            ).count(), 1
        )
        # A *new* request cannot remove a no-longer-active option.
        self.assertEqual(
            self.client.post(url, {"idempotency_key": "different-remove-intent"}).status_code,
            404,
        )

    def test_idempotency_key_cannot_be_reused_for_another_target(self):
        second_plan = SubscriptionPlan.objects.create(
            code="native.billing.alternative", plan_type=SubscriptionPlanType.BASE,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        alternative = PlanVersion.objects.create(
            plan=second_plan, version=1, name="Alternative",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        )
        publish_plan_version(alternative)
        self.client.force_login(self.owner)
        first = reverse("subscriptions_native:plan", args=[self.version.pk])
        second = reverse("subscriptions_native:plan", args=[alternative.pk])
        key = {"idempotency_key": "native-mismatched-intent"}
        self.assertEqual(self.client.post(first, key).status_code, 200)
        self.assertEqual(self.client.post(second, key).status_code, 400)
        self.assertEqual(
            SubscriptionTransition.objects.filter(subscription=self.subscription).count(),
            1,
        )

    def test_pinned_terms_and_billing_are_shared_between_web_and_native(self):
        terms = PlanVersionBillingTerms.objects.create(
            plan_version=self.version, amount="14.50", currency="USD",
            billing_period_unit="month",
        )
        obligation = create_subscription_billing_obligation(
            subscription=self.subscription, billing_terms=terms,
            billing_key="native-web-shared", actor=None,
        )
        self.client.force_login(self.owner)
        home = self.client.get(reverse("subscriptions_native:me"))
        self.assertEqual(home.status_code, 200)
        catalog = home.json()["catalog"]
        row = next(row for row in catalog if row["plan_version_id"] == str(self.version.pk))
        self.assertEqual(row["billing_terms"]["amount"], "14.50")
        self.assertEqual(row["billing_terms"]["period_unit"], "month")
        preview = self.client.get(reverse("subscriptions_native:plan", args=[self.version.pk]))
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["billing_terms"]["amount"], "14.50")
        webpage = self.client.get(reverse("subscriptions:home"))
        self.assertEqual(webpage.status_code, 200)
        self.assertContains(webpage, "14.50")
        self.assertContains(webpage, str(obligation.amount))
        page = self.client.get(reverse("subscriptions:billing"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, obligation.label)
        self.client.force_login(self.other)
        other_page = self.client.get(reverse("subscriptions:billing"))
        self.assertNotContains(other_page, obligation.label)

    def test_personal_billing_query_deduplicates_and_paginates_source_links(self):
        terms = PlanVersionBillingTerms.objects.create(
            plan_version=self.version, amount="5.00", currency="USD",
            billing_period_unit="month",
        )
        for number in range(4):
            create_subscription_billing_obligation(
                subscription=self.subscription, billing_terms=terms,
                billing_key=f"native-page-{number}", actor=None,
            )
        first = personal_billing_obligations(self.subscription, limit=2)
        second = personal_billing_obligations(
            self.subscription, offset=first["next_offset"], limit=2
        )
        self.assertEqual(len(first["items"]), 2)
        self.assertEqual(len(second["items"]), 2)
        self.assertIsNone(second["next_offset"])
        self.assertEqual(
            len({row["id"] for row in first["items"] + second["items"]}), 4
        )
        self.assertEqual(
            {row["status"] for row in first["items"] + second["items"]}, {"pending"}
        )
