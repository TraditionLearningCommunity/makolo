from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from authorization.constants import SystemRoleCode
from authorization.models import AuthorityScope, Mandate, Role
from organizations.models import Organization, Team, TeamMembership
from requirements.contracts import RequirementMode

from operations.subscription_forms import PlanRequirementForm, SubscriptionReviewForm

from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    RequirementDisclosure,
    RequirementFailurePolicy,
    RequirementPhase,
    SubscriptionPlanType,
    SubscriptionSubjectType,
)
from .eligibility_models import PlanRequirement
from .models import PlanVersion, SubscriptionPlan
from .runtime_models import Subscription
from .security_services import request_subscription_transition_for_actor
from .services import publish_plan_version
from .transition_models import SubscriptionTransition


User = get_user_model()


class S6ProductUXTests(TestCase):
    password = "test-only"

    def setUp(self):
        self.actor = User.objects.create_user(
            username="s6-actor",
            email="s6-actor@example.test",
            password=self.password,
        )
        self.other = User.objects.create_user(
            username="s6-other",
            email="s6-other@example.test",
            password=self.password,
        )
        self.profile_subscription = Subscription.objects.get(profile=self.actor)
        self.other_profile_subscription = Subscription.objects.get(profile=self.other)

    def mandate(self, user, role_code, space=None):
        role = Role.objects.get(code=role_code, is_system=True)
        return Mandate.objects.create(
            profile=user,
            role=role,
            scope_type=role.scope_type,
            space=space if role.scope_type == AuthorityScope.SPACE else None,
        )

    def published_base(self, *, code, subject_type, name):
        plan = SubscriptionPlan.objects.create(
            code=code,
            plan_type=SubscriptionPlanType.BASE,
            subject_type=subject_type,
        )
        version = PlanVersion.objects.create(
            plan=plan,
            version=1,
            name=name,
            short_description=f"Description {name}",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        )
        publish_plan_version(version)
        version.refresh_from_db()
        return version

    def test_profile_subscription_page_is_self_scoped(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse("subscriptions:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mon abonnement")
        self.assertNotContains(response, self.other.email)

    def test_preview_is_read_only_and_retry_is_idempotent(self):
        target = self.published_base(
            code="s6.profile.target",
            subject_type=SubscriptionSubjectType.PROFILE,
            name="S6 Profile Target",
        )
        self.client.force_login(self.actor)
        preview_url = reverse("subscriptions:preview", args=[target.pk])
        before = SubscriptionTransition.objects.filter(subscription=self.profile_subscription).count()
        response = self.client.get(preview_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            SubscriptionTransition.objects.filter(subscription=self.profile_subscription).count(),
            before,
        )

        change_url = reverse("subscriptions:change", args=[target.pk])
        payload = {"idempotency_key": "s6-profile-idempotent"}
        first = self.client.post(change_url, payload)
        second = self.client.post(change_url, payload)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(
            SubscriptionTransition.objects.filter(
                subscription=self.profile_subscription,
                idempotency_key="s6-profile-idempotent",
            ).count(),
            1,
        )

    def test_internal_requirement_is_not_disclosed_in_profile_html(self):
        target = self.published_base(
            code="s6.profile.internal",
            subject_type=SubscriptionSubjectType.PROFILE,
            name="S6 Internal Target",
        )
        # Published versions are immutable: build a second target with the requirement before publication.
        plan = SubscriptionPlan.objects.create(
            code="s6.profile.internal.requirement",
            plan_type=SubscriptionPlanType.BASE,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        version = PlanVersion.objects.create(
            plan=plan,
            version=1,
            name="S6 Internal Requirement Target",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
        )
        PlanRequirement.objects.create(
            plan_version=version,
            key="profile.internal.minimum_age",
            title="SECRET INTERNAL CONDITION",
            description="SECRET INTERNAL DETAIL",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="profile.account_age_days",
            config={"operator": ">=", "value": 9999},
            is_mandatory=True,
            failure_policy=RequirementFailurePolicy.BLOCK,
            disclosure=RequirementDisclosure.INTERNAL,
        )
        publish_plan_version(version)
        self.client.force_login(self.actor)
        response = self.client.get(reverse("subscriptions:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "SECRET INTERNAL CONDITION")
        self.assertNotContains(response, "SECRET INTERNAL DETAIL")
        self.assertNotContains(response, "Vérification Makolo")
        self.assertContains(response, target.name)

    def test_profile_transition_action_cannot_target_managed_space_transition(self):
        space = Organization.objects.create(name="S6 Managed Space", created_by=self.actor)
        self.mandate(self.actor, SystemRoleCode.SPACE_OWNER, space)
        space_subscription = Subscription.objects.get(space=space)
        target = self.published_base(
            code="s6.space.target.for-profile-idor",
            subject_type=SubscriptionSubjectType.SPACE,
            name="S6 Space Target",
        )
        transition = request_subscription_transition_for_actor(
            actor=self.actor,
            subscription_id=space_subscription.pk,
            kind="base_switch",
            target_plan_version_id=target.pk,
            request_origin="self_service",
            idempotency_key="s6-space-transition",
        )
        self.client.force_login(self.actor)
        response = self.client.post(reverse("subscriptions:transition-cancel", args=[transition.pk]))
        self.assertEqual(response.status_code, 404)
        transition.refresh_from_db()
        self.assertNotEqual(transition.status, "cancelled")


class S6SpaceUXTests(TestCase):
    password = "test-only"

    def setUp(self):
        self.owner = User.objects.create_user(username="s6-owner", email="s6-owner@example.test", password=self.password)
        self.viewer = User.objects.create_user(username="s6-viewer", email="s6-viewer@example.test", password=self.password)
        self.member = User.objects.create_user(username="s6-member", email="s6-member@example.test", password=self.password)
        self.space = Organization.objects.create(name="S6 Space", created_by=self.owner)
        self.other_space = Organization.objects.create(name="S6 Other Space", created_by=self.owner)
        self.subscription = Subscription.objects.get(space=self.space)
        self.other_subscription = Subscription.objects.get(space=self.other_space)
        self.mandate(self.owner, SystemRoleCode.SPACE_OWNER, self.space)
        self.mandate(self.owner, SystemRoleCode.SPACE_OWNER, self.other_space)
        self.mandate(self.viewer, SystemRoleCode.SPACE_ADMIN, self.space)
        team = Team.objects.create(organization=self.space, name="S6 Team", is_default=True)
        TeamMembership.objects.create(team=team, user=self.member)

    def mandate(self, user, role_code, space=None):
        role = Role.objects.get(code=role_code, is_system=True)
        return Mandate.objects.create(
            profile=user,
            role=role,
            scope_type=role.scope_type,
            space=space if role.scope_type == AuthorityScope.SPACE else None,
        )

    def published_space_base(self, code, name):
        plan = SubscriptionPlan.objects.create(
            code=code,
            plan_type=SubscriptionPlanType.BASE,
            subject_type=SubscriptionSubjectType.SPACE,
        )
        version = PlanVersion.objects.create(plan=plan, version=1, name=name)
        publish_plan_version(version)
        version.refresh_from_db()
        return version

    def test_space_viewer_can_read_but_cannot_mutate(self):
        target = self.published_space_base("s6.space.viewer.target", "S6 Viewer Target")
        self.client.force_login(self.viewer)
        home = reverse("organizations:console-subscription", args=[self.space.slug])
        self.assertEqual(self.client.get(home).status_code, 200)
        preview = reverse("organizations:console-subscription-preview", args=[self.space.slug, target.pk])
        preview_response = self.client.get(preview)
        self.assertEqual(preview_response.status_code, 200)
        self.assertNotContains(preview_response, "Confirmer le changement")
        change = reverse("organizations:console-subscription-change", args=[self.space.slug, target.pk])
        self.assertEqual(self.client.post(change, {"idempotency_key": "viewer-denied"}).status_code, 403)

    def test_team_membership_without_mandate_cannot_open_subscription_console(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("organizations:console-subscription", args=[self.space.slug]))
        self.assertEqual(response.status_code, 403)

    def test_space_transition_action_is_scoped_to_current_space(self):
        target = self.published_space_base("s6.space.other.target", "S6 Other Target")
        transition = request_subscription_transition_for_actor(
            actor=self.owner,
            subscription_id=self.other_subscription.pk,
            kind="base_switch",
            target_plan_version_id=target.pk,
            request_origin="self_service",
            idempotency_key="s6-other-space-transition",
        )
        self.client.force_login(self.owner)
        url = reverse(
            "organizations:console-subscription-transition-cancel",
            args=[self.space.slug, transition.pk],
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        transition.refresh_from_db()
        self.assertNotEqual(transition.status, "cancelled")


class S6StaffHardeningTests(TestCase):
    def test_django_staff_flag_does_not_grant_subscription_operations(self):
        staff = User.objects.create_user(
            username="s6-django-staff",
            email="s6-django-staff@example.test",
            password="test-only",
            is_staff=True,
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("operations:subscriptions"))
        self.assertEqual(response.status_code, 403)

    def test_platform_mandate_grants_subscription_operations(self):
        actor = User.objects.create_user(username="s6-platform", email="s6-platform@example.test", password="test-only")
        role = Role.objects.get(code=SystemRoleCode.PLATFORM_ADMIN, is_system=True)
        Mandate.objects.create(profile=actor, role=role, scope_type=AuthorityScope.PLATFORM)
        self.client.force_login(actor)
        self.assertEqual(self.client.get(reverse("operations:subscriptions")).status_code, 200)
        self.assertEqual(self.client.get(reverse("operations:subscription-catalog")).status_code, 200)

    def test_staff_forms_accept_dotted_codes_and_reject_unknown_evaluator(self):
        review = SubscriptionReviewForm(
            data={
                "state": "satisfied",
                "reason_code": "subscription.review.staff_decision",
                "note": "ok",
            }
        )
        self.assertTrue(review.is_valid(), review.errors)

        form = PlanRequirementForm(
            data={
                "key": "space.member_count.minimum",
                "title": "Minimum membres",
                "description": "",
                "phase": "acquisition",
                "mode": "automatic",
                "evaluator_key": "unknown.evaluator",
                "operator": ">=",
                "threshold": 1,
                "mandatory": "on",
                "disclosure": "visible",
                "position": 0,
                "failure_policy": "block",
                "grace_period_days": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("evaluator_key", form.errors)
