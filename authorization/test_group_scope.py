from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from groups.services import create_group

from .constants import PermissionCode, SystemRoleCode
from .models import AuthorityScope, Mandate, MandateStatus
from .services import can, grant_group_role, group_ids_with_permission, revoke_mandate


User = get_user_model()


class GroupScopeAuthorizationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="auth-group-owner",
            email="auth-group-owner@example.com",
            password="Password123!",
        )
        self.delegate = User.objects.create_user(
            username="auth-group-delegate",
            email="auth-group-delegate@example.com",
            password="Password123!",
        )
        self.group_a = create_group(actor=self.owner, name="Auth Groupe A")
        self.group_b = create_group(actor=self.owner, name="Auth Groupe B")

    def test_group_scope_shape_has_group_only(self):
        mandate = grant_group_role(
            profile=self.delegate,
            group=self.group_a,
            role=SystemRoleCode.GROUP_ADMIN,
            granted_by=self.owner,
        )
        self.assertEqual(mandate.scope_type, AuthorityScope.GROUP)
        self.assertEqual(mandate.group, self.group_a)
        self.assertIsNone(mandate.space)

    def test_group_scope_db_validation_rejects_space_target(self):
        role = self.group_a.authority_mandates.filter(
            role__code=SystemRoleCode.GROUP_OWNER
        ).select_related("role").first().role
        mandate = Mandate(
            profile=self.delegate,
            role=role,
            scope_type=AuthorityScope.GROUP,
            group=self.group_a,
            space_id="00000000-0000-0000-0000-000000000001",
        )
        with self.assertRaises(ValidationError):
            mandate.full_clean()

    def test_can_keeps_positional_space_contract_and_group_keyword(self):
        grant_group_role(
            profile=self.delegate,
            group=self.group_a,
            role=SystemRoleCode.GROUP_ADMIN,
            granted_by=self.owner,
        )
        self.assertTrue(can(self.delegate, PermissionCode.GROUP_MANAGE, group=self.group_a))
        self.assertFalse(can(self.delegate, PermissionCode.GROUP_MANAGE, group=self.group_b))

    def test_group_ids_with_permission_is_contextual(self):
        grant_group_role(
            profile=self.delegate,
            group=self.group_a,
            role=SystemRoleCode.GROUP_MODERATOR,
            granted_by=self.owner,
        )
        self.assertEqual(
            set(group_ids_with_permission(self.delegate, PermissionCode.GROUP_MEMBERS_MANAGE)),
            {self.group_a.pk},
        )

    def test_expired_group_mandate_does_not_authorize(self):
        mandate = grant_group_role(
            profile=self.delegate,
            group=self.group_a,
            role=SystemRoleCode.GROUP_ADMIN,
            granted_by=self.owner,
        )
        mandate.valid_until = timezone.now() - timedelta(seconds=1)
        mandate.save(update_fields=["valid_until", "updated_at"])
        self.assertFalse(can(self.delegate, PermissionCode.GROUP_MANAGE, group=self.group_a))

    def test_revoke_group_mandate_is_postgresql_safe_path(self):
        mandate = grant_group_role(
            profile=self.delegate,
            group=self.group_a,
            role=SystemRoleCode.GROUP_ADMIN,
            granted_by=self.owner,
        )
        revoked = revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(revoked.status, MandateStatus.REVOKED)
        self.assertFalse(can(self.delegate, PermissionCode.GROUP_MANAGE, group=self.group_a))
