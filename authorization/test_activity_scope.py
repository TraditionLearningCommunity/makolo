from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.services import create_activity
from organizations.models import Organization

from .constants import PermissionCode, SystemRoleCode
from .models import AuthorityScope, Mandate, MandateStatus
from .services import can, grant_activity_role, grant_space_role, get_system_role


User = get_user_model()


class ActivityAuthorityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="activity-space-owner", email="owner-activity@example.test", password="StrongPass2026!")
        self.local = User.objects.create_user(username="activity-local", email="local-activity@example.test", password="StrongPass2026!")
        self.space_a = Organization.objects.create(name="Space Activity A", created_by=self.owner)
        self.space_b = Organization.objects.create(name="Space Activity B", created_by=self.owner)
        self.activity_a = create_activity(space=self.space_a, created_by=self.owner, title="Activity A")
        self.activity_b = create_activity(space=self.space_b, created_by=self.owner, title="Activity B")
        grant_space_role(profile=self.owner, space=self.space_a, role=SystemRoleCode.SPACE_OWNER)

    def test_space_portfolio_authority_is_inherited_only_inside_space(self):
        self.assertTrue(can(self.owner, PermissionCode.ACTIVITY_MANAGE, activity=self.activity_a))
        self.assertFalse(can(self.owner, PermissionCode.ACTIVITY_MANAGE, activity=self.activity_b))

    def test_activity_local_mandate_is_isolated_from_other_activity_and_space(self):
        grant_activity_role(profile=self.local, activity=self.activity_a)
        self.assertTrue(can(self.local, PermissionCode.ACTIVITY_MANAGE, activity=self.activity_a))
        self.assertFalse(can(self.local, PermissionCode.ACTIVITY_MANAGE, activity=self.activity_b))
        self.assertFalse(can(self.local, PermissionCode.FINANCE_MANAGE, self.space_a))
        self.assertFalse(can(self.local, PermissionCode.SPACE_TEAM_MANAGE, self.space_a))
        self.assertFalse(can(self.local, PermissionCode.SPACE_GROUPS_MANAGE, self.space_a))
        self.assertFalse(can(self.local, PermissionCode.SPACE_PLACES_MANAGE, self.space_a))

    def test_expired_and_revoked_activity_mandates_are_refused(self):
        role = get_system_role(SystemRoleCode.ACTIVITY_MANAGER, scope_type=AuthorityScope.ACTIVITY)
        expired = Mandate.objects.create(
            profile=self.local, role=role, scope_type=AuthorityScope.ACTIVITY, activity=self.activity_a,
            status=MandateStatus.ACTIVE, valid_from=timezone.now()-timedelta(days=2), valid_until=timezone.now()-timedelta(days=1),
        )
        self.assertFalse(can(self.local, PermissionCode.ACTIVITY_MANAGE, activity=self.activity_a))
        expired.status = MandateStatus.REVOKED
        expired.revoked_at = timezone.now()
        expired.save(update_fields=["status", "revoked_at", "updated_at"])
        self.assertFalse(can(self.local, PermissionCode.ACTIVITY_MANAGE, activity=self.activity_a))
