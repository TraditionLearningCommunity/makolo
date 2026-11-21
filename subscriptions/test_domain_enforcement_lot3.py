from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from activities.models import Activity
from activities.services import create_activity
from authorization.constants import SystemRoleCode
from organizations.models import Organization, TeamMembership, TeamMembershipStatus
from organizations.services import add_or_update_member, create_organization
from subscriptions.entitlements import EffectiveEntitlementResult


User = get_user_model()


class SubscriptionDomainEnforcementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="s3-enforcement-owner", email="s3-enforcement-owner@example.test",
            password="test-only",
        )
        self.member = User.objects.create_user(
            username="s3-enforcement-member", email="s3-enforcement-member@example.test",
            password="test-only",
        )
        self.space = create_organization(creator=self.owner, name="S3 Enforcement Space")

    def result(self, code, *, value, allowed, usage=None):
        return EffectiveEntitlementResult(
            feature_code=code, effective_value=value, sources=(), usage=usage,
            allowed=allowed, reason_code="allowed" if allowed else "limit_reached",
        )

    def test_activity_creation_is_scoped_to_actual_profile_or_space_owner(self):
        seen = []

        def fake_resolve(subject, code):
            seen.append((subject.pk, code))
            return self.result(code, value=False, allowed=False)

        with patch("activities.services.resolve_entitlement", side_effect=fake_resolve):
            with self.assertRaises(ValidationError):
                create_activity(created_by=self.owner, owner_profile=self.owner, title="Denied Personal")
            with self.assertRaises(ValidationError):
                create_activity(created_by=self.owner, space=self.space, title="Denied Space")
        self.assertEqual(seen, [
            (self.owner.pk, "activities.create"),
            (self.space.pk, "activities.create"),
        ])
        self.assertFalse(Activity.objects.filter(title__startswith="Denied").exists())

    def test_team_limit_blocks_new_member_without_creating_mandate(self):
        with patch("subscriptions.entitlements.resolve_entitlement", return_value=self.result("team.members", value=1, allowed=False, usage=1)):
            with self.assertRaises(ValidationError):
                add_or_update_member(
                    organization=self.space, actor=self.owner, user=self.member,
                    role=SystemRoleCode.SPACE_ADMIN,
                )
        self.assertFalse(TeamMembership.objects.filter(
            team__organization=self.space, user=self.member,
            status=TeamMembershipStatus.ACTIVE,
        ).exists())

    def test_team_limit_does_not_block_existing_member_responsibility_change(self):
        with patch("subscriptions.entitlements.resolve_entitlement", return_value=self.result("team.members", value=2, allowed=True, usage=1)):
            first = add_or_update_member(
                organization=self.space, actor=self.owner, user=self.member,
                role=SystemRoleCode.FINANCE,
            )
        with patch("subscriptions.entitlements.resolve_entitlement", side_effect=AssertionError("no quota on edit")):
            second = add_or_update_member(
                organization=self.space, actor=self.owner, user=self.member,
                role=SystemRoleCode.SPACE_ADMIN,
            )
        self.assertEqual(first.pk, second.pk)

    def test_unconfigured_team_limit_preserves_existing_base_behavior(self):
        with patch("subscriptions.entitlements.resolve_entitlement", return_value=self.result("team.members", value=None, allowed=False)):
            membership = add_or_update_member(
                organization=self.space, actor=self.owner, user=self.member,
                role=SystemRoleCode.SPACE_ADMIN,
            )
        self.assertEqual(membership.status, TeamMembershipStatus.ACTIVE)
