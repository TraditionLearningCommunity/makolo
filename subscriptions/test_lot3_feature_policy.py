"""Lot 3: pinned FALSE BASE and non-escalating custom role composition."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from activities.models import Activity
from activities.services import create_activity
from authorization.constants import PermissionCode
from authorization.services import create_custom_space_role
from organizations.services import create_organization
from subscriptions.contracts import SubscriptionPlanType, SubscriptionSubjectType
from subscriptions.entitlements import resolve_entitlement
from subscriptions.models import FeatureDefinition, PlanEntitlement, PlanVersion, SubscriptionPlan
from subscriptions.runtime_models import Subscription
from subscriptions.runtime_services import (
    add_subscription_item, create_entitlement_grant, end_subscription_item,
)
from subscriptions.services import publish_plan_version


User = get_user_model()


class FeaturePolicyConsumerTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="lot3-policy-owner", password="test-only")
        self.space = create_organization(creator=self.owner, name="Lot 3 policy Space")

    def test_published_false_base_disables_new_personal_activity_without_affecting_space(self):
        feature = FeatureDefinition.objects.get(code="activities.create")
        plan = SubscriptionPlan.objects.create(
            code="lot3.profile.no_creation",
            plan_type=SubscriptionPlanType.BASE,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        version = PlanVersion.objects.create(
            plan=plan, version=1, name="Profile creation disabled",
        )
        PlanEntitlement.objects.create(
            plan_version=version, feature=feature, value=False,
        )
        publish_plan_version(version)
        subscription = Subscription.objects.get(profile=self.owner)
        current = subscription.items.get(status="active", item_type="base")
        end_subscription_item(item=current, reason="Test pinned base replacement")
        add_subscription_item(subscription=subscription, plan_version=version)
        resolved = resolve_entitlement(self.owner, "activities.create")
        self.assertIs(resolved.effective_value, False)
        self.assertFalse(resolved.allowed)
        self.assertEqual(resolved.reason_code, "feature_disabled")
        with self.assertRaises(ValidationError):
            create_activity(
                owner_profile=self.owner, created_by=self.owner,
                title="Denied by false entitlement",
            )
        self.assertFalse(Activity.objects.filter(title="Denied by false entitlement").exists())
        collective = create_activity(
            space=self.space, created_by=self.owner, title="Owner is the Space",
        )
        self.assertEqual(collective.space_id, self.space.pk)

    def test_custom_role_permission_composition_never_grants_a_mandate(self):
        create_entitlement_grant(
            feature=FeatureDefinition.objects.get(code="custom_roles"),
            value=True, space=self.space,
            reason="Lot3 authorized role composition", granted_by=self.owner,
        )
        role = create_custom_space_role(
            actor=self.owner, space=self.space, code="team-coordination",
            name="Team coordination",
            permission_codes=(PermissionCode.SPACE_TEAM_MANAGE,),
        )
        self.assertEqual(role.permissions.count(), 1)
        self.assertFalse(role.mandates.exists())
        self.assertTrue(role.permissions.filter(code=PermissionCode.SPACE_TEAM_MANAGE).exists())
        with self.assertRaises(ValidationError):
            create_custom_space_role(
                actor=self.owner, space=self.space, code="platform-authority",
                name="Forbidden platform role",
                permission_codes=(PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE,),
            )
