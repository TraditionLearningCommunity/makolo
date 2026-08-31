from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, Permission, Role, RolePermission
from organizations.models import Organization

from .authorization import get_space_subscription_for_actor
from .contracts import FeatureEnforcementPolicy, FeatureValueType
from .models import FeatureDefinition
from .runtime_models import Subscription
from .security_services import create_entitlement_grant_for_actor


User = get_user_model()


class S5AuthorizedFacadeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="s5-owner", email="s5-owner@example.test", password="test-only")
        self.space = Organization.objects.create(name="S5 Facade Space", created_by=self.owner)
        self.subscription = Subscription.objects.get(space=self.space)

    def test_django_staff_without_platform_mandate_has_no_subscription_authority(self):
        staff = User.objects.create_user(
            username="s5-django-staff",
            email="s5-django-staff@example.test",
            password="test-only",
            is_staff=True,
        )
        with self.assertRaises(Http404):
            get_space_subscription_for_actor(staff, self.subscription.pk)

    def test_custom_space_role_can_delegate_manage(self):
        actor = User.objects.create_user(username="s5-delegate", email="s5-delegate@example.test", password="test-only")
        permission = Permission.objects.get(code=PermissionCode.SPACE_SUBSCRIPTION_MANAGE)
        role = Role.objects.create(
            code="subscription-manager",
            name="Subscription Manager",
            scope_type=AuthorityScope.SPACE,
            organization=self.space,
            is_system=False,
        )
        RolePermission.objects.create(role=role, permission=permission)
        Mandate.objects.create(
            profile=actor,
            role=role,
            scope_type=AuthorityScope.SPACE,
            space=self.space,
        )
        self.assertEqual(
            get_space_subscription_for_actor(actor, self.subscription.pk, manage=True),
            self.subscription,
        )

    def test_grant_creation_requires_platform_grants_permission(self):
        feature = FeatureDefinition.objects.create(
            code="s5.grant.feature",
            name="Grant feature",
            domain="subscriptions",
            value_type=FeatureValueType.BOOLEAN,
            supports_profile=False,
            supports_space=True,
            aggregation_strategy="BOOLEAN_OR",
            enforcement_policy=FeatureEnforcementPolicy.FEATURE_GATE,
        )
        with self.assertRaises(PermissionDenied):
            create_entitlement_grant_for_actor(
                actor=self.owner,
                feature=feature,
                value=True,
                reason="test denied",
                space=self.space,
            )

        platform_actor = User.objects.create_user(
            username="s5-platform",
            email="s5-platform@example.test",
            password="test-only",
        )
        platform_role = Role.objects.get(code=SystemRoleCode.PLATFORM_ADMIN, is_system=True)
        Mandate.objects.create(
            profile=platform_actor,
            role=platform_role,
            scope_type=AuthorityScope.PLATFORM,
        )
        grant = create_entitlement_grant_for_actor(
            actor=platform_actor,
            feature=feature,
            value=True,
            reason="test authorized",
            space=self.space,
        )
        self.assertEqual(grant.granted_by, platform_actor)
