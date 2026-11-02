"""Lot 4: Subscription handoff and safe action continuation, no authority transfer."""
from urllib.parse import parse_qs, urlencode, urlsplit

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Permission, Role, RolePermission
from authorization.services import grant_space_role
from organizations.services import create_organization
from subscriptions.models import FeatureDefinition, PlanVersion, SubscriptionPlan
from subscriptions.runtime_models import Subscription
from subscriptions.contracts import SubscriptionPlanType, SubscriptionSubjectType
from subscriptions.services import publish_plan_version
from subscriptions.runtime_services import create_entitlement_grant
from subscriptions.ux_continuation import (
    action_subscription_handoff,
    is_subscription_denial,
    safe_action_return,
    subscription_return_home,
)

User = get_user_model()


class SubscriptionContinuationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="lot4-owner", email="lot4-owner@example.test", password="test-only",
        )
        self.teammate = User.objects.create_user(
            username="lot4-teammate", email="lot4-teammate@example.test", password="test-only",
        )
        self.manager = User.objects.create_user(
            username="lot4-manager", email="lot4-manager@example.test", password="test-only",
        )
        self.space = create_organization(creator=self.owner, name="Lot4 One Space")
        self.other = create_organization(creator=self.owner, name="Lot4 Other Space")
        self.factory = RequestFactory()

    def _limit_one(self):
        create_entitlement_grant(
            space=self.space,
            feature=FeatureDefinition.objects.get(code="team.members"),
            value=1,
            reason="Lot4 active-member quota example",
        )

    def test_personal_activity_denial_links_only_to_profile_subscription(self):
        subscription = Subscription.objects.get(profile=self.owner)
        subscription.status = "suspended"
        subscription.save(update_fields=["status"])
        self.client.force_login(self.owner)
        create_url = reverse("activities:create")
        response = self.client.post(create_url, {
            "title": "An action to continue",
            "short_description": "",
            "description": "",
            "visibility": "private",
            "organization": "",
        })
        self.assertEqual(response.status_code, 200)
        handoff = response.context["subscription_handoff"]
        self.assertIn(reverse("subscriptions:home"), handoff["url"])
        self.assertNotIn(self.space.slug + "/subscription", handoff["url"])
        next_path = parse_qs(urlsplit(handoff["url"]).query)["next"][0]
        self.assertEqual(next_path, create_url)
        landing = self.client.get(handoff["url"])
        self.assertEqual(landing.status_code, 200)
        self.assertContains(landing, "Revenir à l’action")
        self.assertContains(landing, create_url)

    def test_space_team_quota_handoff_preserves_exact_space_and_action(self):
        self._limit_one()
        self.client.force_login(self.owner)
        target = reverse("organizations:team-member-create", args=[self.space.slug])
        response = self.client.post(target, {
            "email": self.teammate.email,
            "role": SystemRoleCode.SPACE_ADMIN,
        })
        self.assertEqual(response.status_code, 400)
        handoff = response.context["subscription_handoff"]
        self.assertIsNotNone(handoff)
        self.assertTrue(handoff["url"].startswith(
            reverse("organizations:console-subscription", args=[self.space.slug])
        ))
        next_path = parse_qs(urlsplit(handoff["url"]).query)["next"][0]
        self.assertEqual(next_path, target)
        self.assertContains(response, "Comprendre dans l’abonnement", status_code=400)
        landing = self.client.get(handoff["url"])
        self.assertEqual(landing.status_code, 200)
        self.assertContains(landing, "Revenir à l’action")
        self.assertContains(landing, target)
        self.assertNotContains(landing, self.other.slug + "/subscription")

    def test_team_manager_without_subscription_mandate_gets_no_financial_handoff(self):
        self._limit_one()
        role = Role.objects.create(
            code="lot4-team-only", name="Team authority only",
            scope_type=AuthorityScope.SPACE, organization=self.space,
        )
        permission = Permission.objects.get(code=PermissionCode.SPACE_TEAM_MANAGE)
        RolePermission.objects.create(role=role, permission=permission)
        grant_space_role(profile=self.manager, space=self.space, role=role)
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("organizations:team-member-create", args=[self.space.slug]),
            {"email": self.teammate.email, "role": SystemRoleCode.SPACE_ADMIN},
        )
        self.assertEqual(response.status_code, 400)
        handoff = response.context["subscription_handoff"]
        self.assertIsNone(handoff["url"])
        self.assertContains(response, "Une personne autorisée", status_code=400)
        self.assertNotContains(response, "Comprendre dans l’abonnement", status_code=400)

    def test_return_path_allowlist_rejects_external_cross_space_and_privileged_depths(self):
        team = reverse("organizations:team-member-create", args=[self.space.slug])
        other_team = reverse("organizations:team-member-create", args=[self.other.slug])
        cases = (
            "//evil.invalid/path",
            "https://evil.invalid/path",
            "/\\evil.invalid/path",
            "/admin/",
            reverse("subscriptions:home"),
            other_team,
            reverse("activities:create"),
            reverse("activities:create") + "?space=" + self.other.slug,
        )
        for value in cases:
            with self.subTest(value=value):
                request = self.factory.get(
                    reverse("organizations:console-subscription", args=[self.space.slug]),
                    {"next": value},
                )
                request.user = self.owner
                self.assertIsNone(safe_action_return(request, space=self.space))
        request = self.factory.get(
            reverse("organizations:console-subscription", args=[self.space.slug]),
            {"next": team},
        )
        request.user = self.owner
        self.assertEqual(safe_action_return(request, space=self.space), team)

    def test_preview_and_post_keep_the_same_return_link(self):
        self.client.force_login(self.owner)
        action = reverse("organizations:team-member-create", args=[self.space.slug])
        plan = SubscriptionPlan.objects.create(
            code="lot4.space.preview", plan_type=SubscriptionPlanType.BASE,
            subject_type=SubscriptionSubjectType.SPACE,
        )
        version = PlanVersion.objects.create(
            plan=plan, version=1, name="Lot 4 Visible Space Plan",
        )
        publish_plan_version(version)
        preview = reverse(
            "organizations:console-subscription-preview",
            args=[self.space.slug, version.pk],
        )
        response = self.client.get(preview + "?" + urlencode({"next": action}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="next"')
        back = reverse(
            "organizations:console-subscription", args=[self.space.slug],
        )
        self.assertContains(response, back + "?next=")
        changed = self.client.post(
            reverse(
                "organizations:console-subscription-change",
                args=[self.space.slug, version.pk],
            ),
            {"idempotency_key": "lot4-preview-once", "next": action},
        )
        self.assertEqual(changed.status_code, 302)
        self.assertEqual(changed["Location"], back + "?" + urlencode({"next": action}))

    def test_post_confirmation_keeps_only_validated_continuation(self):
        team = reverse("organizations:team-member-create", args=[self.space.slug])
        home = reverse("organizations:console-subscription", args=[self.space.slug])
        request = self.factory.post(home, {"next": team})
        self.assertEqual(
            subscription_return_home(request, space=self.space),
            home + "?next=" + urlencode({"next": team}),
        )
        forged = self.factory.post(home, {"next": "//evil.invalid"})
        self.assertEqual(subscription_return_home(forged, space=self.space), home)

    def test_non_subscription_validation_never_offers_upgrade(self):
        from django.core.exceptions import ValidationError
        self.assertFalse(is_subscription_denial(ValidationError({"email": "Invalid"})))
        self.assertTrue(is_subscription_denial(ValidationError({"subscription": "Blocked"})))
