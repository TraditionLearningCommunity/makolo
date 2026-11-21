"""Lot 3: server-side enforcement by Activity, Organizations and Authorization.

Technical BASEs and all feature values are the existing Subscription truth.
No new plan, price, capability or persistent usage counter is required.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from activities.services import create_activity, update_activity_common
from authorization.constants import SystemRoleCode
from authorization.models import AuthorityScope, Role
from authorization.services import create_custom_space_role, grant_space_role
from organizations.models import OrganizationMembership, OrganizationRole, TeamMembership, TeamMembershipStatus
from organizations.services import (
    add_existing_collaborator_to_team,
    add_or_update_member,
    create_organization,
    create_team,
)
from subscriptions.entitlements import resolve_entitlement
from subscriptions.models import FeatureDefinition, PlanEntitlement, PlanVersion, SubscriptionPlan
from subscriptions.runtime_services import add_subscription_item, end_subscription_item
from subscriptions.services import publish_plan_version
from subscriptions.runtime_services import create_entitlement_grant, revoke_entitlement_grant

User = get_user_model()


class RuntimeFeatureEnforcementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="lot3-owner", password="test-only")
        self.second = User.objects.create_user(username="lot3-second", password="test-only")
        self.third = User.objects.create_user(username="lot3-third", password="test-only")
        self.space = create_organization(creator=self.owner, name="Lot 3 Space")
        self.other_space = create_organization(creator=self.owner, name="Other Lot 3 Space")

    def grant(self, subject, feature_code, value):
        args = {"space": subject} if subject.__class__.__name__ == "Organization" else {"profile": subject}
        return create_entitlement_grant(
            feature=FeatureDefinition.objects.get(code=feature_code),
            value=value, reason="Test enforcement owner", **args,
        )

    def test_activity_creation_uses_owning_subject_not_acting_profile(self):
        self.grant(self.owner, "activities.create", False)
        # False GRANT and BASE True are combined by BOOLEAN_OR: the grant does
        # not remove the BASE. A suspended subscription provides the real gate.
        from subscriptions.runtime_models import Subscription
        profile_subscription = Subscription.objects.get(profile=self.owner)
        profile_subscription.status = "suspended"
        profile_subscription.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            create_activity(owner_profile=self.owner, created_by=self.owner, title="Blocked personal")
        self.assertFalse(Activity.objects.filter(title="Blocked personal").exists())

        created = create_activity(space=self.space, created_by=self.owner, title="Allowed Space")
        self.assertEqual(created.space_id, self.space.pk)
        space_subscription = Subscription.objects.get(space=self.space)
        space_subscription.status = "suspended"
        space_subscription.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            create_activity(space=self.space, created_by=self.owner, title="Blocked Space")
        self.assertFalse(Activity.objects.filter(title="Blocked Space").exists())
        # Existing real work remains editable, even if new acquisition stops.
        update_activity_common(activity=created, title="Existing work preserved")
        created.refresh_from_db()
        self.assertEqual(created.title, "Existing work preserved")
        self.assertTrue(
            create_activity(space=self.other_space, created_by=self.owner, title="Other Space allowed")
        )

    def test_explicit_false_base_blocks_only_its_profile(self):
        from subscriptions.runtime_models import Subscription
        from subscriptions.contracts import SubscriptionPlanType, SubscriptionSubjectType
        alternate_plan = SubscriptionPlan.objects.create(
            code="lot3.profile.disabled-create",
            plan_type=SubscriptionPlanType.BASE,
            subject_type=SubscriptionSubjectType.PROFILE,
        )
        alternate_version = PlanVersion.objects.create(
            plan=alternate_plan, version=1, name="Profile without Activity create",
        )
        PlanEntitlement.objects.create(
            plan_version=alternate_version,
            feature=FeatureDefinition.objects.get(code="activities.create"),
            value=False,
        )
        publish_plan_version(alternate_version)
        subscription = Subscription.objects.get(profile=self.owner)
        old_base = subscription.items.get(status="active", item_type="base")
        end_subscription_item(item=old_base, reason="Test declared false capability")
        add_subscription_item(subscription=subscription, plan_version=alternate_version)
        self.assertFalse(resolve_entitlement(self.owner, "activities.create").allowed)
        with self.assertRaises(ValidationError):
            create_activity(
                owner_profile=self.owner, created_by=self.owner,
                title="False BASE blocks profile",
            )
        self.assertTrue(
            create_activity(
                space=self.space, created_by=self.owner,
                title="Space BASE remains independent",
            )
        )

    def test_activity_web_form_displays_denial_instead_of_server_error(self):
        from subscriptions.runtime_models import Subscription
        subscription = Subscription.objects.get(profile=self.owner)
        subscription.status = "suspended"
        subscription.save(update_fields=["status"])
        self.client.force_login(self.owner)
        response = self.client.post(reverse("activities:create"), {
            "title": "Not permitted by Subscription",
            "short_description": "",
            "description": "",
            "visibility": "private",
            "organization": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La création")
        self.assertFalse(Activity.objects.filter(
            title="Not permitted by Subscription",
        ).exists())

    def test_unconfigured_team_quota_never_becomes_zero(self):
        entitlement = resolve_entitlement(self.space, "team.members")
        self.assertIsNone(entitlement.effective_value)
        member = add_or_update_member(
            organization=self.space, actor=self.owner, user=self.second,
            role=SystemRoleCode.SPACE_ADMIN,
        )
        self.assertEqual(member.status, TeamMembershipStatus.ACTIVE)

    def test_configured_quota_blocks_only_new_unique_profiles(self):
        # Owner already occupies the one slot; no new active Profile is admitted.
        self.grant(self.space, "team.members", 1)
        with self.assertRaises(ValidationError):
            add_or_update_member(
                organization=self.space, actor=self.owner, user=self.second,
                role=SystemRoleCode.SPACE_ADMIN,
            )
        self.assertFalse(TeamMembership.objects.filter(
            team__organization=self.space, user=self.second,
            status=TeamMembershipStatus.ACTIVE,
        ).exists())

        # Raising the quota with another canonical SUM grant opens one slot.
        self.grant(self.space, "team.members", 1)
        membership = add_or_update_member(
            organization=self.space, actor=self.owner, user=self.second,
            role=SystemRoleCode.SPACE_ADMIN,
        )
        self.assertEqual(resolve_entitlement(self.space, "team.members").usage, 2)
        with self.assertRaises(ValidationError):
            add_or_update_member(
                organization=self.space, actor=self.owner, user=self.third,
                role=SystemRoleCode.SPACE_ADMIN,
            )

        # Reassigning an already counted member or adding them to a second
        # Team must not consume another slot, grant new authority or be blocked.
        add_or_update_member(
            organization=self.space, actor=self.owner, user=self.second,
            role=SystemRoleCode.FINANCE,
        )
        secondary = create_team(organization=self.space, actor=self.owner, name="Second team")
        extra = add_existing_collaborator_to_team(
            team=secondary, actor=self.owner, user=self.second,
        )
        self.assertEqual(extra.status, TeamMembershipStatus.ACTIVE)
        self.assertEqual(resolve_entitlement(self.space, "team.members").usage, 2)
        self.assertEqual(membership.user_id, extra.user_id)

    def test_legacy_projection_is_rejected_before_quota_write(self):
        self.grant(self.space, "team.members", 1)
        with self.assertRaises(ValidationError):
            OrganizationMembership.objects.create(
                organization=self.space, user=self.second,
                role=OrganizationRole.EVENT_MANAGER, invited_by=self.owner,
                is_active=True,
            )
        self.assertFalse(OrganizationMembership.objects.filter(
            organization=self.space, user=self.second,
        ).exists())

    def test_reactivated_legacy_member_respects_quota(self):
        self.grant(self.space, "team.members", 1)
        legacy = OrganizationMembership.objects.create(
            organization=self.space, user=self.second,
            role=OrganizationRole.EVENT_MANAGER, invited_by=self.owner,
            is_active=False,
        )
        legacy.is_active = True
        with self.assertRaises(ValidationError):
            legacy.save()
        legacy.refresh_from_db()
        self.assertFalse(legacy.is_active)
        self.assertFalse(TeamMembership.objects.filter(
            team__organization=self.space, user=self.second,
            status=TeamMembershipStatus.ACTIVE,
        ).exists())

    def test_custom_role_creation_needs_both_authority_and_entitlement(self):
        with self.assertRaises(ValidationError):
            create_custom_space_role(
                actor=self.owner, space=self.space,
                code="our-coordinator", name="Coordination",
            )
        self.assertFalse(Role.objects.filter(
            organization=self.space, code="our-coordinator",
        ).exists())
        self.grant(self.space, "custom_roles", True)
        with self.assertRaises(PermissionDenied):
            create_custom_space_role(
                actor=self.second, space=self.space,
                code="unauthorized", name="No authority",
            )
        role = create_custom_space_role(
            actor=self.owner, space=self.space,
            code="our-coordinator", name="Coordination",
        )
        self.assertEqual(role.scope_type, AuthorityScope.SPACE)
        self.assertFalse(role.is_system)
        with self.assertRaises(ValidationError):
            create_custom_space_role(
                actor=self.owner, space=self.space,
                code="our-coordinator", name="Duplicated",
            )
        with self.assertRaises(ValidationError):
            create_custom_space_role(
                actor=self.owner, space=self.other_space,
                code="other-space-role", name="Not transferred",
            )
        # Existing Role and existing authority are not deleted by plan change.
        mandate = grant_space_role(
            profile=self.second, space=self.space, role=role,
            granted_by=self.owner,
        )
        self.assertEqual(mandate.role_id, role.pk)
        self.assertTrue(Role.objects.filter(pk=role.pk).exists())
        self.grant(self.space, "custom_roles", False)
        # BOOLEAN_OR keeps the earlier true grant in place. Revoking it,
        # however, must prevent only future creation, never delete history.
        true_grant = next(
            row for row in self.space.entitlement_grants.filter(
                feature__code="custom_roles",
            ) if row.value is True
        )
        revoke_entitlement_grant(grant=true_grant, actor=self.owner, reason="Test downgrade")
        with self.assertRaises(ValidationError):
            create_custom_space_role(
                actor=self.owner, space=self.space,
                code="after-downgrade", name="Nouveau rôle interdit",
            )
        self.assertTrue(Role.objects.filter(pk=role.pk).exists())
