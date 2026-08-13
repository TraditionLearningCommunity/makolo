from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from organizations.models import Organization

from .constants import PermissionCode, SystemRoleCode
from .models import AuthorityScope, Mandate, MandateStatus, Permission, Role, RolePermission
from .services import (
    can,
    can_many,
    effective_permission_codes,
    ensure_platform_admin_mandate,
    get_system_role,
    grant_space_role,
    replace_standard_space_role,
    revoke_mandate,
)

User = get_user_model()


class AuthorityModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="authority-user", email="authority-user@makolo.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="Authority Space", created_by=self.user)
        self.space_role = Role.objects.create(code="test-space-role", name="Test space role", scope_type=AuthorityScope.SPACE, organization=self.space, is_system=False)
        self.permission = Permission.objects.create(code="test.space.permission", name="Test permission", domain="test", scope_type=AuthorityScope.SPACE, is_system=False)
        RolePermission.objects.create(role=self.space_role, permission=self.permission)

    def test_platform_scope_rejects_space_target(self):
        role = Role.objects.create(code="test-platform", name="Test platform", scope_type=AuthorityScope.PLATFORM, is_system=True)
        mandate = Mandate(profile=self.user, role=role, scope_type=AuthorityScope.PLATFORM, space=self.space)
        with self.assertRaises(ValidationError): mandate.full_clean()

    def test_space_scope_requires_space_target(self):
        mandate = Mandate(profile=self.user, role=self.space_role, scope_type=AuthorityScope.SPACE)
        with self.assertRaises(ValidationError): mandate.full_clean()

    def test_validity_window_rejects_end_before_start(self):
        now = timezone.now()
        mandate = Mandate(profile=self.user, role=self.space_role, scope_type=AuthorityScope.SPACE, space=self.space, valid_from=now, valid_until=now-timedelta(minutes=1))
        with self.assertRaises(ValidationError): mandate.full_clean()

    def test_role_permission_requires_same_scope(self):
        platform_permission = Permission.objects.create(code="test.platform.permission", name="Platform permission", domain="test", scope_type=AuthorityScope.PLATFORM, is_system=False)
        link = RolePermission(role=self.space_role, permission=platform_permission)
        with self.assertRaises(ValidationError): link.full_clean()


class AuthorityResolutionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", email="owner@makolo.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="other", email="other@makolo.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="Authority Space", created_by=self.owner)
        self.other_space = Organization.objects.create(name="Other Space", created_by=self.other)

    def test_space_mandate_grants_only_target_space(self):
        grant_space_role(profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_ADMIN)
        self.assertTrue(can(self.owner, PermissionCode.SPACE_MANAGE, self.space))
        self.assertFalse(can(self.owner, PermissionCode.SPACE_MANAGE, self.other_space))

    def test_team_member_without_mandate_has_no_authority(self):
        from organizations.models import TeamMembership, TeamMembershipStatus
        team = self.space.teams.get(is_default=True)
        TeamMembership.objects.create(team=team, user=self.other, status=TeamMembershipStatus.ACTIVE, joined_at=timezone.now())
        self.assertFalse(can(self.other, PermissionCode.SPACE_VIEW, self.space))

    def test_mandate_without_permission_is_refused(self):
        role = Role.objects.create(code="empty-role", name="Empty role", scope_type=AuthorityScope.SPACE, organization=self.space, is_system=False)
        Mandate.objects.create(profile=self.other, role=role, scope_type=AuthorityScope.SPACE, space=self.space)
        self.assertFalse(can(self.other, PermissionCode.FINANCE_VIEW, self.space))

    def test_expired_future_revoked_and_inactive_roles_are_refused(self):
        role = get_system_role(SystemRoleCode.FINANCE)
        now = timezone.now()
        future = Mandate.objects.create(profile=self.other, role=role, scope_type=AuthorityScope.SPACE, space=self.space, valid_from=now+timedelta(days=1))
        self.assertFalse(can(self.other, PermissionCode.FINANCE_VIEW, self.space))
        future.delete()
        expired = Mandate.objects.create(profile=self.other, role=role, scope_type=AuthorityScope.SPACE, space=self.space, valid_from=now-timedelta(days=2), valid_until=now-timedelta(days=1))
        self.assertFalse(can(self.other, PermissionCode.FINANCE_VIEW, self.space))
        expired.delete()
        revoked = Mandate.objects.create(profile=self.other, role=role, scope_type=AuthorityScope.SPACE, space=self.space, status=MandateStatus.REVOKED, revoked_at=now)
        self.assertFalse(can(self.other, PermissionCode.FINANCE_VIEW, self.space))
        revoked.delete()
        role.is_active = False; role.save(update_fields=["is_active", "updated_at"])
        Mandate.objects.create(profile=self.other, role=role, scope_type=AuthorityScope.SPACE, space=self.space)
        self.assertFalse(can(self.other, PermissionCode.FINANCE_VIEW, self.space))

    def test_can_many_uses_same_permission_resolution(self):
        grant_space_role(profile=self.owner, space=self.space, role=SystemRoleCode.FINANCE)
        result = can_many(self.owner, [PermissionCode.FINANCE_VIEW, PermissionCode.MARKETING_MANAGE], self.space)
        self.assertEqual(result, {PermissionCode.FINANCE_VIEW: True, PermissionCode.MARKETING_MANAGE: False})

    def test_platform_admin_can_resolve_all_business_permissions(self):
        ensure_platform_admin_mandate(profile=self.owner, source="test")
        self.assertTrue(can(self.owner, PermissionCode.FINANCE_VIEW, self.other_space))
        self.assertTrue(can(self.owner, PermissionCode.CRM_MANAGE, self.other_space))

    def test_superuser_is_technical_break_glass(self):
        superuser = User.objects.create_superuser(username="root", email="root@makolo.test", password="StrongPass2026!")
        self.assertTrue(can(superuser, PermissionCode.FINANCE_VIEW, self.space))

    def test_standard_roles_remain_strictly_separated(self):
        expectations = {
            SystemRoleCode.FINANCE: {PermissionCode.FINANCE_MANAGE: True, PermissionCode.MARKETING_MANAGE: False, PermissionCode.CRM_MANAGE: False},
            SystemRoleCode.MARKETING: {PermissionCode.MARKETING_MANAGE: True, PermissionCode.FINANCE_MANAGE: False, PermissionCode.ANALYTICS_FINANCIALS_VIEW: False},
            SystemRoleCode.ACCESS_MANAGER: {PermissionCode.ACCESS_MANAGE: True, PermissionCode.FINANCE_VIEW: False, PermissionCode.CRM_VIEW: False},
            SystemRoleCode.SPACE_ACTIVITY_MANAGER: {PermissionCode.SPACE_ACTIVITIES_MANAGE: True, PermissionCode.FINANCE_VIEW: False, PermissionCode.FINANCE_MANAGE: False},
        }
        for index, (role_code, checks) in enumerate(expectations.items()):
            profile = User.objects.create_user(username=f"role-{index}", email=f"role-{index}@makolo.test", password="StrongPass2026!")
            grant_space_role(profile=profile, space=self.space, role=role_code)
            for permission_code, expected in checks.items():
                self.assertEqual(can(profile, permission_code, self.space), expected, f"{role_code} / {permission_code}")

    def test_new_staff_user_has_no_implicit_business_authority(self):
        staff = User.objects.create_user(username="new-staff", email="new-staff@makolo.test", password="StrongPass2026!", is_staff=True)
        self.assertFalse(can(staff, PermissionCode.FINANCE_VIEW, self.space))
        self.assertFalse(can(staff, PermissionCode.SPACE_MANAGE, self.space))
        ensure_platform_admin_mandate(profile=staff, source="test")
        self.assertTrue(can(staff, PermissionCode.FINANCE_VIEW, self.space))

    def test_replacing_last_owner_is_blocked(self):
        mandate = grant_space_role(profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER)
        with self.assertRaises(ValidationError): revoke_mandate(mandate=mandate, actor=self.owner)

    def test_owner_can_be_removed_after_second_owner_exists(self):
        first = grant_space_role(profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER)
        grant_space_role(profile=self.other, space=self.space, role=SystemRoleCode.SPACE_OWNER)
        revoke_mandate(mandate=first, actor=self.other)
        first.refresh_from_db(); self.assertEqual(first.status, MandateStatus.REVOKED)

    def test_replace_standard_space_role_preserves_owner_invariant(self):
        grant_space_role(profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER)
        with self.assertRaises(ValidationError): replace_standard_space_role(profile=self.owner, space=self.space, role_code=SystemRoleCode.SPACE_ADMIN)
