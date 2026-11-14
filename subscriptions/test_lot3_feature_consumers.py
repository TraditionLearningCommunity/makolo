"""Lot 3: three seeded Feature consumers, owner scoping and no extra authority."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from activities.models import Activity
from activities.services import create_activity
from authorization.constants import SystemRoleCode
from authorization.services import create_custom_space_role
from authorization.models import Role
from organizations.models import TeamMembership, TeamMembershipStatus
from organizations.services import (
    add_existing_collaborator_to_team,
    add_or_update_member,
    create_organization,
    create_team,
)
from subscriptions.entitlements import resolve_entitlement
from subscriptions.models import FeatureDefinition
from subscriptions.runtime_models import Subscription
from subscriptions.runtime_services import create_entitlement_grant


User = get_user_model()


class FeatureConsumerTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="feature-owner", password="only-test")
        self.colleague = User.objects.create_user(username="feature-colleague", password="only-test")
        self.other = User.objects.create_user(username="feature-third", password="only-test")
        self.space = create_organization(creator=self.owner, name="Feature quota Space")
        self.second = create_organization(creator=self.owner, name="Another feature Space")

    def grant(self, code, value):
        return create_entitlement_grant(
            feature=FeatureDefinition.objects.get(code=code),
            value=value, space=self.space, granted_by=self.owner,
            reason="Feature consumer test",
        )

    def test_activity_creation_checks_owning_subject_not_actors_plan(self):
        personal = create_activity(
            owner_profile=self.owner, created_by=self.owner, title="Existing personal",
        )
        collective = create_activity(
            space=self.space, created_by=self.owner, title="Existing collective",
        )
        profile_sub = Subscription.objects.get(profile=self.owner)
        profile_sub.status = "suspended"
        profile_sub.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            create_activity(
                owner_profile=self.owner, created_by=self.owner, title="Denied personal",
            )
        allowed = create_activity(
            space=self.space, created_by=self.owner, title="Space still allowed",
        )
        self.assertEqual(allowed.space_id, self.space.pk)
        space_sub = Subscription.objects.get(space=self.space)
        space_sub.status = "suspended"
        space_sub.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            create_activity(space=self.space, created_by=self.owner, title="Denied Space")
        self.assertEqual(Activity.objects.filter(pk__in=[personal.pk, collective.pk]).count(), 2)
        self.assertFalse(Activity.objects.filter(title="Denied Space").exists())
        self.assertTrue(resolve_entitlement(self.second, "activities.create").allowed)

    def test_team_quota_blocks_new_distinct_people_but_preserves_members_and_reassignment(self):
        # Technical base intentionally has no numeric quota, not a zero quota.
        self.assertIsNone(resolve_entitlement(self.space, "team.members").effective_value)
        self.grant("team.members", 2)
        add_or_update_member(
            organization=self.space, actor=self.owner,
            user=self.colleague, role=SystemRoleCode.SPACE_ADMIN,
        )
        self.assertEqual(resolve_entitlement(self.space, "team.members").usage, 2)
        with self.assertRaises(ValidationError):
            add_or_update_member(
                organization=self.space, actor=self.owner,
                user=self.other, role=SystemRoleCode.SPACE_ADMIN,
            )
        self.assertFalse(TeamMembership.objects.filter(
            team__organization=self.space, user=self.other,
            status=TeamMembershipStatus.ACTIVE,
        ).exists())
        add_or_update_member(
            organization=self.space, actor=self.owner,
            user=self.colleague, role=SystemRoleCode.SPACE_ADMIN,
        )
        secondary = create_team(organization=self.space, actor=self.owner, name="Ops")
        add_existing_collaborator_to_team(
            team=secondary, actor=self.owner, user=self.colleague,
        )
        self.assertEqual(resolve_entitlement(self.space, "team.members").usage, 2)
        self.assertIsNone(resolve_entitlement(self.second, "team.members").effective_value)

    def test_custom_roles_require_permission_and_space_entitlement_without_granting_authority(self):
        with self.assertRaises(ValidationError):
            create_custom_space_role(
                space=self.space, actor=self.owner,
                code="coordinator", name="Coordination",
            )
        self.grant("custom_roles", True)
        with self.assertRaises(PermissionDenied):
            create_custom_space_role(
                space=self.space, actor=self.other,
                code="forged", name="Not authorized",
            )
        role = create_custom_space_role(
            space=self.space, actor=self.owner,
            code="coordinator", name="Coordination",
        )
        self.assertFalse(role.is_system)
        self.assertEqual(role.organization_id, self.space.pk)
        self.assertEqual(role.permissions.count(), 0)
        self.assertFalse(role.mandates.exists())
        with self.assertRaises(ValidationError):
            create_custom_space_role(
                space=self.second, actor=self.owner,
                code="coordinator", name="Another Space cannot inherit",
            )
        with self.assertRaises(ValidationError):
            create_custom_space_role(
                space=self.space, actor=self.owner,
                code="coordinator", name="Duplicate",
            )
        role.refresh_from_db()
        self.assertEqual(role.name, "Coordination")
