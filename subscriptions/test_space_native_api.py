"""Space Subscription native contract: exact actor, exact Space, existing Mandates."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from authorization.constants import SystemRoleCode
from authorization.models import AuthorityScope, Mandate, Role
from organizations.models import Organization, Team, TeamMembership
from organizations.api.space_us_projection import build_space_us_projection

from .billing_models import PlanVersionBillingTerms
from .billing_services import create_subscription_billing_obligation
from .contracts import AcquisitionMode, CatalogVisibility, SubscriptionPlanType, SubscriptionSubjectType
from .models import PlanVersion, SubscriptionPlan
from .runtime_models import Subscription
from .security_services import request_subscription_transition_for_actor
from .transition_models import SubscriptionTransition

User = get_user_model()


class NativeSpaceSubscriptionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="space-native-owner", password="test-only")
        self.viewer = User.objects.create_user(username="space-native-viewer", password="test-only")
        self.member = User.objects.create_user(username="space-native-member", password="test-only")
        self.space = Organization.objects.create(name="Native Subscription Space", created_by=self.owner)
        self.other_space = Organization.objects.create(name="Native Other Subscription Space", created_by=self.owner)
        self.subscription = Subscription.objects.get(space=self.space)
        self.other_subscription = Subscription.objects.get(space=self.other_space)
        self._mandate(self.owner, SystemRoleCode.SPACE_OWNER, self.space)
        self._mandate(self.owner, SystemRoleCode.SPACE_OWNER, self.other_space)
        self._mandate(self.viewer, SystemRoleCode.SPACE_ADMIN, self.space)
        team = Team.objects.create(organization=self.space, name="Native team", is_default=True)
        TeamMembership.objects.create(team=team, user=self.member)
        plan = SubscriptionPlan.objects.create(
            code="native.space.subscription.target",
            plan_type=SubscriptionPlanType.BASE,
            subject_type=SubscriptionSubjectType.SPACE,
        )
        self.version = PlanVersion.objects.create(
            plan=plan, version=1, name="Formule Space test",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        )
        from .services import publish_plan_version
        publish_plan_version(self.version)

    def _mandate(self, actor, role_code, space):
        role = Role.objects.get(code=role_code, is_system=True)
        return Mandate.objects.create(
            profile=actor, role=role, scope_type=AuthorityScope.SPACE, space=space
        )

    def _url(self, name, *params, slug=None):
        return reverse("subscriptions_native:" + name, args=[slug or self.space.slug, *params])

    def test_space_read_requires_mandate_not_team_membership(self):
        url = self._url("space")
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.viewer)
        result = self.client.get(url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["Cache-Control"], "private, no-store")
        payload = result.json()
        self.assertEqual(payload["space"]["id"], str(self.space.pk))
        self.assertEqual(payload["subscription"]["id"], str(self.subscription.pk))
        self.assertEqual(payload["subscription"]["subject_type"], "space")
        self.assertFalse(payload["subscription"]["can_manage"])
        self.assertNotIn(str(self.other_subscription.pk), str(payload))
        self.assertNotIn(str(Subscription.objects.get(profile=self.viewer).pk), str(payload))

    def test_view_permission_can_preview_but_never_request_transition(self):
        self.client.force_login(self.viewer)
        page = self.client.get(self._url("space")).json()
        option = next(r for r in page["catalog"] if r["plan_version_id"] == str(self.version.pk))
        self.assertTrue(option["can_preview"])
        self.assertFalse(option["can_request"])
        preview = self.client.get(self._url("space-plan", self.version.pk))
        self.assertEqual(preview.status_code, 200)
        self.assertFalse(preview.json()["can_confirm"])
        result = self.client.post(
            self._url("space-plan", self.version.pk),
            {"idempotency_key": "viewer-space-no-authority"},
        )
        self.assertEqual(result.status_code, 404)
        self.assertFalse(SubscriptionTransition.objects.filter(subscription=self.subscription).exists())

    def test_owner_changes_plan_using_existing_services_and_replays_intent(self):
        self.client.force_login(self.owner)
        url = self._url("space-plan", self.version.pk)
        key = {"idempotency_key": "space-native-stable-intent"}
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, key).status_code, 200)
        self.assertEqual(self.client.post(url, key).status_code, 200)
        self.assertEqual(
            SubscriptionTransition.objects.filter(
                subscription=self.subscription, idempotency_key=key["idempotency_key"]
            ).count(), 1
        )
        history = self.client.get(self._url("space-history"))
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()["items"]), 1)
        self.assertEqual(
            history.json()["items"][0]["target_name"], "Formule Space test"
        )

    def test_transition_mutations_cannot_cross_space_boundary(self):
        self.client.force_login(self.owner)
        transition = request_subscription_transition_for_actor(
            actor=self.owner,
            subscription_id=self.other_subscription.pk,
            kind="base_switch", target_plan_version_id=self.version.pk,
            request_origin="self_service", idempotency_key="space-other-intent",
        )
        for operation in ("cancel", "complete"):
            response = self.client.post(self._url("space-transition", transition.pk, operation))
            self.assertEqual(response.status_code, 404)
        transition.refresh_from_db()
        self.assertNotEqual(transition.status, "cancelled")

    def test_space_billing_terms_and_obligations_do_not_leak_to_profile(self):
        terms = PlanVersionBillingTerms.objects.create(
            plan_version=self.version, amount="18.00",
            currency="USD", billing_period_unit="month",
        )
        obligation = create_subscription_billing_obligation(
            subscription=self.subscription, billing_terms=terms,
            billing_key="space-native-obligation", actor=None,
        )
        self.client.force_login(self.owner)
        snapshot = self.client.get(self._url("space")).json()
        row = next(r for r in snapshot["catalog"] if r["plan_version_id"] == str(self.version.pk))
        self.assertEqual(row["billing_terms"]["amount"], "18.00")
        self.assertIn(str(obligation.pk), [r["id"] for r in snapshot["billing"]["items"]])
        own_billing = self.client.get(self._url("space-obligations"))
        self.assertEqual(own_billing.status_code, 200)
        self.assertEqual(own_billing.json()["items"][0]["id"], str(obligation.pk))
        self.assertNotIn(
            str(obligation.pk),
            str(self.client.get(reverse("subscriptions_native:me")).json()),
        )
        self.assertNotIn(
            str(obligation.pk),
            str(self.client.get(self._url("space", slug=self.other_space.slug)).json()),
        )
        web = self.client.get(
            reverse("organizations:console-subscription", args=[self.space.slug])
        )
        self.assertEqual(web.status_code, 200)
        self.assertContains(web, obligation.label)
        self.assertEqual(
            self.client.get(reverse("organizations:console-subscription-billing", args=[self.space.slug])).status_code,
            200,
        )

    def test_manage_only_permission_also_allows_read_for_exact_space(self):
        from unittest.mock import patch
        from authorization.constants import PermissionCode
        from .authorization import subscriptions_visible_to_actor

        def scope(_actor, code):
            if code == PermissionCode.SPACE_SUBSCRIPTION_MANAGE:
                return [self.space.pk]
            if code == PermissionCode.SPACE_SUBSCRIPTION_VIEW:
                return []
            return []

        with patch("subscriptions.authorization.space_ids_with_permission", side_effect=scope):
            visible = subscriptions_visible_to_actor(self.member)
            manageable = subscriptions_visible_to_actor(self.member, manage=True)
            self.assertTrue(visible.filter(pk=self.subscription.pk).exists())
            self.assertTrue(manageable.filter(pk=self.subscription.pk).exists())
            self.assertFalse(visible.filter(pk=self.other_subscription.pk).exists())
            self.assertFalse(manageable.filter(pk=self.other_subscription.pk).exists())

    def test_nous_handoff_respects_subscription_mandate(self):
        owner = build_space_us_projection(profile=self.owner, space=self.space)
        self.assertEqual(owner["handoffs"]["subscription"], f"/space/{self.space.slug}/subscription")
        viewer = build_space_us_projection(profile=self.viewer, space=self.space)
        self.assertEqual(viewer["handoffs"]["subscription"], f"/space/{self.space.slug}/subscription")
