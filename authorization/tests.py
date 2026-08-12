from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus

from .constants import PermissionCode, SystemRoleCode
from .models import AuthorityScope, Mandate, MandateStatus, Permission, Role, RolePermission
from .services import (
    can,
    can_many,
    ensure_platform_admin_mandate,
    get_system_role,
    grant_space_role,
    revoke_mandate,
)


User = get_user_model()


class MandateModelTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="profile",
            email="profile@authority.test",
            password="StrongPass2026!",
        )
        self.creator = User.objects.create_user(
            username="creator",
            email="creator@authority.test",
            password="StrongPass2026!",
        )
        self.space = Organization.objects.create(name="Authority Space", created_by=self.creator)
        self.space_role = get_system_role(SystemRoleCode.FINANCE)
        self.platform_role = get_system_role(
            SystemRoleCode.PLATFORM_ADMIN,
            scope_type=AuthorityScope.PLATFORM,
        )

    def test_platform_scope_rejects_space(self):
        mandate = Mandate(
            profile=self.profile,
            role=self.platform_role,
            scope_type=AuthorityScope.PLATFORM,
            space=self.space,
        )
        with self.assertRaises(ValidationError):
            mandate.full_clean()

    def test_space_scope_requires_space(self):
        mandate = Mandate(
            profile=self.profile,
            role=self.space_role,
            scope_type=AuthorityScope.SPACE,
        )
        with self.assertRaises(ValidationError):
            mandate.full_clean()

    def test_role_scope_must_match_mandate_scope(self):
        mandate = Mandate(
            profile=self.profile,
            role=self.platform_role,
            scope_type=AuthorityScope.SPACE,
            space=self.space,
        )
        with self.assertRaises(ValidationError):
            mandate.full_clean()

    def test_valid_until_must_follow_valid_from(self):
        now = timezone.now()
        mandate = Mandate(
            profile=self.profile,
            role=self.space_role,
            scope_type=AuthorityScope.SPACE,
            space=self.space,
            valid_from=now,
            valid_until=now - timedelta(minutes=1),
        )
        with self.assertRaises(ValidationError):
            mandate.full_clean()

    def test_database_rejects_invalid_scope_shape(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Mandate.objects.create(
                profile=self.profile,
                role=self.space_role,
                scope_type=AuthorityScope.SPACE,
                space=None,
            )

    def test_active_space_mandate_is_unique(self):
        grant_space_role(profile=self.profile, space=self.space, role=self.space_role)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Mandate.objects.create(
                profile=self.profile,
                role=self.space_role,
                scope_type=AuthorityScope.SPACE,
                space=self.space,
                status=MandateStatus.ACTIVE,
            )

    def test_custom_space_role_cannot_receive_platform_permission(self):
        role = Role.objects.create(
            code="custom-finance",
            name="Finance personnalisée",
            scope_type=AuthorityScope.SPACE,
            organization=self.space,
            is_system=False,
        )
        platform_permission = Permission.objects.get(code=PermissionCode.PLATFORM_MANAGE)
        link = RolePermission(role=role, permission=platform_permission)
        with self.assertRaises(ValidationError):
            link.full_clean()


class AuthorityResolutionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner-auth",
            email="owner-auth@makolo.test",
            password="StrongPass2026!",
        )
        self.profile = User.objects.create_user(
            username="worker-auth",
            email="worker-auth@makolo.test",
            password="StrongPass2026!",
        )
        self.other_owner = User.objects.create_user(
            username="owner-other",
            email="owner-other@makolo.test",
            password="StrongPass2026!",
        )
        self.space = Organization.objects.create(name="Space A", created_by=self.owner)
        self.other_space = Organization.objects.create(name="Space B", created_by=self.other_owner)

    def test_permission_is_scoped_to_the_right_space(self):
        grant_space_role(profile=self.profile, space=self.space, role=SystemRoleCode.FINANCE)
        self.assertTrue(can(self.profile, PermissionCode.FINANCE_VIEW, self.space))
        self.assertTrue(can(self.profile, PermissionCode.FINANCE_MANAGE, self.space))
        self.assertFalse(can(self.profile, PermissionCode.FINANCE_VIEW, self.other_space))

    def test_team_member_without_mandate_has_no_authority(self):
        team = Team.objects.create(
            organization=self.space,
            name="Équipe principale",
            is_default=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=self.profile,
            status=TeamMembershipStatus.ACTIVE,
            joined_at=timezone.now(),
        )
        self.assertFalse(can(self.profile, PermissionCode.SPACE_VIEW, self.space))
        self.assertFalse(can(self.profile, PermissionCode.FINANCE_VIEW, self.space))

    def test_role_without_permission_does_not_grant_it(self):
        role = Role.objects.create(
            code="custom-empty",
            name="Sans permission",
            scope_type=AuthorityScope.SPACE,
            organization=self.space,
        )
        grant_space_role(profile=self.profile, space=self.space, role=role)
        self.assertFalse(can(self.profile, PermissionCode.SPACE_VIEW, self.space))

    def test_future_expired_revoked_and_suspended_mandates_are_denied(self):
        now = timezone.now()
        finance = get_system_role(SystemRoleCode.FINANCE)

        future = Mandate.objects.create(
            profile=self.profile,
            role=finance,
            scope_type=AuthorityScope.SPACE,
            space=self.space,
            valid_from=now + timedelta(hours=1),
        )
        self.assertFalse(can(self.profile, PermissionCode.FINANCE_VIEW, self.space))
        future.status = MandateStatus.REVOKED
        future.revoked_at = now
        future.save(update_fields=["status", "revoked_at"])

        expired = Mandate.objects.create(
            profile=self.profile,
            role=finance,
            scope_type=AuthorityScope.SPACE,
            space=self.space,
            valid_from=now - timedelta(hours=2),
            valid_until=now - timedelta(hours=1),
        )
        self.assertFalse(can(self.profile, PermissionCode.FINANCE_VIEW, self.space))
        expired.status = MandateStatus.REVOKED
        expired.revoked_at = now
        expired.save(update_fields=["status", "revoked_at"])

        suspended = Mandate.objects.create(
            profile=self.profile,
            role=finance,
            scope_type=AuthorityScope.SPACE,
            space=self.space,
            status=MandateStatus.SUSPENDED,
        )
        self.assertFalse(can(self.profile, PermissionCode.FINANCE_VIEW, self.space))
        suspended.status = MandateStatus.REVOKED
        suspended.revoked_at = now
        suspended.save(update_fields=["status", "revoked_at"])

        active = grant_space_role(profile=self.profile, space=self.space, role=finance)
        self.assertTrue(can(self.profile, PermissionCode.FINANCE_VIEW, self.space))
        revoke_mandate(mandate=active)
        self.assertFalse(can(self.profile, PermissionCode.FINANCE_VIEW, self.space))

    def test_inactive_role_and_inactive_permission_are_denied(self):
        finance = get_system_role(SystemRoleCode.FINANCE)
        mandate = grant_space_role(profile=self.profile, space=self.space, role=finance)
        self.assertTrue(can(self.profile, PermissionCode.FINANCE_VIEW, self.space))

        finance.is_active = False
        finance.save(update_fields=["is_active"])
        self.assertFalse(can(self.profile, PermissionCode.FINANCE_VIEW, self.space))

        finance.is_active = True
        finance.save(update_fields=["is_active"])
        permission = Permission.objects.get(code=PermissionCode.FINANCE_VIEW)
        permission.is_active = False
        permission.save(update_fields=["is_active"])
        self.assertFalse(can(self.profile, PermissionCode.FINANCE_VIEW, self.space))

        mandate.refresh_from_db()
        self.assertEqual(mandate.status, MandateStatus.ACTIVE)

    def test_standard_roles_remain_strictly_separated(self):
        expectations = {
            SystemRoleCode.FINANCE: {
                PermissionCode.FINANCE_MANAGE: True,
                PermissionCode.MARKETING_MANAGE: False,
                PermissionCode.CRM_MANAGE: False,
            },
            SystemRoleCode.MARKETING: {
                PermissionCode.MARKETING_MANAGE: True,
                PermissionCode.FINANCE_MANAGE: False,
                PermissionCode.ANALYTICS_FINANCIALS_VIEW: False,
            },
            SystemRoleCode.ACCESS_MANAGER: {
                PermissionCode.ACCESS_MANAGE: True,
                PermissionCode.FINANCE_VIEW: False,
                PermissionCode.CRM_VIEW: False,
            },
            SystemRoleCode.ACTIVITY_MANAGER: {
                PermissionCode.ACTIVITY_MANAGE: True,
                PermissionCode.FINANCE_VIEW: False,
                PermissionCode.FINANCE_MANAGE: False,
            },
        }
        for index, (role_code, checks) in enumerate(expectations.items()):
            profile = User.objects.create_user(
                username=f"role-{index}",
                email=f"role-{index}@makolo.test",
                password="StrongPass2026!",
            )
            grant_space_role(profile=profile, space=self.space, role=role_code)
            for permission_code, expected in checks.items():
                self.assertEqual(
                    can(profile, permission_code, self.space),
                    expected,
                    f"{role_code} / {permission_code}",
                )

    def test_new_staff_user_has_no_implicit_business_authority(self):
        staff = User.objects.create_user(
            username="new-staff",
            email="new-staff@makolo.test",
            password="StrongPass2026!",
            is_staff=True,
        )
        self.assertFalse(can(staff, PermissionCode.FINANCE_VIEW, self.space))
        self.assertFalse(can(staff, PermissionCode.SPACE_MANAGE, self.space))

        ensure_platform_admin_mandate(profile=staff, source="test")
        self.assertTrue(can(staff, PermissionCode.FINANCE_VIEW, self.space))
        self.assertTrue(can(staff, PermissionCode.SPACE_MANAGE, self.other_space))

    def test_superuser_retains_technical_global_authority(self):
        superuser = User.objects.create_superuser(
            username="root-auth",
            email="root-auth@makolo.test",
            password="StrongPass2026!",
        )
        self.assertTrue(can(superuser, PermissionCode.FINANCE_MANAGE, self.space))
        self.assertTrue(can(superuser, PermissionCode.CRM_MANAGE, self.other_space))

    def test_can_many_resolves_multiple_capabilities(self):
        grant_space_role(profile=self.profile, space=self.space, role=SystemRoleCode.FINANCE)
        result = can_many(
            self.profile,
            [PermissionCode.FINANCE_VIEW, PermissionCode.FINANCE_MANAGE, PermissionCode.CRM_MANAGE],
            self.space,
        )
        self.assertEqual(
            result,
            {
                PermissionCode.FINANCE_VIEW: True,
                PermissionCode.FINANCE_MANAGE: True,
                PermissionCode.CRM_MANAGE: False,
            },
        )
