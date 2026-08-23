from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.manual_grants import grant_access_manually
from activities.models import Activity
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, MandateStatus, Permission, Role
from authorization.services import can, grant_activity_role, grant_space_role

from .models import OrganizationMembership, OrganizationRole, TeamMembership, TeamMembershipStatus
from .services import add_or_update_member, create_organization
from .team_responsibilities import (
    grant_member_activity_responsibility,
    remove_member_from_space,
    revoke_member_activity_responsibility,
    update_member_space_responsibility,
)


User = get_user_model()


class TeamResponsibilityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="task19-owner", email="task19-owner@example.test", password="StrongPass2026!")
        self.admin = User.objects.create_user(username="task19-admin", email="task19-admin@example.test", password="StrongPass2026!")
        self.member = User.objects.create_user(username="task19-member", email="task19-member@example.test", password="StrongPass2026!")
        self.beneficiary = User.objects.create_user(username="task19-beneficiary", email="task19-beneficiary@example.test", password="StrongPass2026!")
        self.space = create_organization(creator=self.owner, name="Task 19 Space")
        self.other_space = create_organization(creator=self.owner, name="Task 19 Other")
        add_or_update_member(organization=self.space, actor=self.owner, user=self.admin, role=SystemRoleCode.SPACE_ADMIN)
        self.membership = add_or_update_member(organization=self.space, actor=self.owner, user=self.member, role=SystemRoleCode.FINANCE)
        self.activity_a = Activity.objects.create(space=self.space, created_by=self.owner, title="Activity A")
        self.activity_b = Activity.objects.create(space=self.space, created_by=self.owner, title="Activity B")
        self.other_activity = Activity.objects.create(space=self.other_space, created_by=self.owner, title="Activity Other")

    def test_team_membership_without_mandate_has_no_business_authority(self):
        team_only = User.objects.create_user(username="task19-team-only", email="task19-team-only@example.test", password="StrongPass2026!")
        TeamMembership.objects.create(
            team=self.space.teams.get(is_default=True),
            user=team_only,
            status=TeamMembershipStatus.ACTIVE,
            joined_at=timezone.now(),
        )
        for code in (
            PermissionCode.SPACE_MANAGE,
            PermissionCode.SPACE_TEAM_MANAGE,
            PermissionCode.FINANCE_VIEW,
            PermissionCode.CRM_MANAGE,
        ):
            self.assertFalse(can(team_only, code, self.space))
        self.assertFalse(can(team_only, PermissionCode.ACTIVITY_MANAGE, activity=self.activity_a))
        self.assertFalse(can(team_only, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=self.activity_a))

    def test_standard_space_change_is_idempotent_preserves_custom_other_space_and_legacy(self):
        permission = Permission.objects.get(code=PermissionCode.SPACE_VIEW)
        custom = Role.objects.create(
            code="task19-custom",
            name="Responsable personnalisé",
            scope_type=AuthorityScope.SPACE,
            organization=self.space,
            is_system=False,
            is_active=True,
        )
        custom.permissions.add(permission)
        grant_space_role(profile=self.member, space=self.space, role=custom, granted_by=self.owner)
        grant_space_role(profile=self.member, space=self.other_space, role=SystemRoleCode.ACCESS_MANAGER, granted_by=self.owner)
        joined_at = self.membership.joined_at

        update_member_space_responsibility(
            membership=self.membership,
            actor=self.owner,
            role_code=SystemRoleCode.MARKETING,
        )
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.joined_at, joined_at)
        self.assertFalse(can(self.member, PermissionCode.FINANCE_VIEW, self.space))
        self.assertTrue(can(self.member, PermissionCode.MARKETING_MANAGE, self.space))
        self.assertTrue(Mandate.objects.filter(profile=self.member, space=self.space, role=custom, status=MandateStatus.ACTIVE).exists())
        self.assertTrue(Mandate.objects.filter(profile=self.member, space=self.other_space, role__code=SystemRoleCode.ACCESS_MANAGER, status=MandateStatus.ACTIVE).exists())
        legacy = OrganizationMembership.objects.get(organization=self.space, user=self.member)
        self.assertEqual(legacy.role, OrganizationRole.MARKETING)

        active_before = Mandate.objects.filter(profile=self.member, space=self.space, role__code=SystemRoleCode.MARKETING, status=MandateStatus.ACTIVE).count()
        update_member_space_responsibility(membership=self.membership, actor=self.owner, role_code=SystemRoleCode.MARKETING)
        self.assertEqual(Mandate.objects.filter(profile=self.member, space=self.space, role__code=SystemRoleCode.MARKETING, status=MandateStatus.ACTIVE).count(), active_before)

    def test_admin_cannot_promote_downgrade_or_remove_owner(self):
        owner_membership = TeamMembership.objects.get(team__organization=self.space, user=self.owner)
        with self.assertRaises(PermissionDenied):
            update_member_space_responsibility(membership=self.membership, actor=self.admin, role_code=SystemRoleCode.SPACE_OWNER)
        self.assertFalse(Mandate.objects.filter(profile=self.member, space=self.space, role__code=SystemRoleCode.SPACE_OWNER, status=MandateStatus.ACTIVE).exists())
        with self.assertRaises(PermissionDenied):
            update_member_space_responsibility(membership=owner_membership, actor=self.admin, role_code=SystemRoleCode.SPACE_ADMIN)
        with self.assertRaises(PermissionDenied):
            remove_member_from_space(membership=owner_membership, actor=self.admin)

    def test_owner_can_add_coowner_and_last_owner_invariant_remains(self):
        second_owner = User.objects.create_user(username="task19-owner-two", email="task19-owner-two@example.test", password="StrongPass2026!")
        second_membership = add_or_update_member(organization=self.space, actor=self.owner, user=second_owner, role=SystemRoleCode.SPACE_ADMIN)
        update_member_space_responsibility(membership=second_membership, actor=self.owner, role_code=SystemRoleCode.SPACE_OWNER)
        self.assertTrue(can(second_owner, PermissionCode.SPACE_OWNERSHIP_MANAGE, self.space))

        owner_membership = TeamMembership.objects.get(team__organization=self.space, user=self.owner)
        update_member_space_responsibility(membership=owner_membership, actor=self.owner, role_code=SystemRoleCode.SPACE_ADMIN)
        self.assertFalse(can(self.owner, PermissionCode.SPACE_OWNERSHIP_MANAGE, self.space))
        self.assertTrue(can(second_owner, PermissionCode.SPACE_OWNERSHIP_MANAGE, self.space))

        with self.assertRaises(ValidationError):
            update_member_space_responsibility(membership=second_membership, actor=second_owner, role_code=SystemRoleCode.SPACE_ADMIN)
        self.assertTrue(can(second_owner, PermissionCode.SPACE_OWNERSHIP_MANAGE, self.space))

    def test_activity_roles_are_local_multiple_and_idempotent(self):
        manager = grant_member_activity_responsibility(
            membership=self.membership,
            actor=self.owner,
            activity=self.activity_a,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
        )
        scanner = grant_member_activity_responsibility(
            membership=self.membership,
            actor=self.owner,
            activity=self.activity_a,
            role_code=SystemRoleCode.ACTIVITY_SCANNER,
        )
        scanner_again = grant_member_activity_responsibility(
            membership=self.membership,
            actor=self.owner,
            activity=self.activity_a,
            role_code=SystemRoleCode.ACTIVITY_SCANNER,
        )
        self.assertEqual(scanner.pk, scanner_again.pk)
        self.assertNotEqual(manager.pk, scanner.pk)
        self.assertTrue(can(self.member, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=self.activity_a))
        self.assertFalse(can(self.member, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=self.activity_b))
        self.assertTrue(can(self.member, PermissionCode.ACTIVITY_ACCESS_MANAGE, activity=self.activity_a))
        self.assertFalse(can(self.member, PermissionCode.ACTIVITY_ACCESS_MANAGE, activity=self.activity_b))

        revoke_member_activity_responsibility(membership=self.membership, actor=self.owner, mandate=scanner)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, TeamMembershipStatus.ACTIVE)
        scanner.refresh_from_db()
        manager.refresh_from_db()
        self.assertEqual(scanner.status, MandateStatus.REVOKED)
        self.assertEqual(manager.status, MandateStatus.ACTIVE)

    def test_activity_and_role_scope_forgery_is_rejected(self):
        with self.assertRaises(ValidationError):
            grant_member_activity_responsibility(
                membership=self.membership,
                actor=self.owner,
                activity=self.other_activity,
                role_code=SystemRoleCode.ACTIVITY_SCANNER,
            )
        with self.assertRaises(ValidationError):
            grant_member_activity_responsibility(
                membership=self.membership,
                actor=self.owner,
                activity=self.activity_a,
                role_code=SystemRoleCode.FINANCE,
            )
        with self.assertRaises(ValidationError):
            update_member_space_responsibility(
                membership=self.membership,
                actor=self.owner,
                role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            )

    def test_remove_member_revokes_space_and_local_activity_authority_only(self):
        local_a = grant_activity_role(profile=self.member, activity=self.activity_a, role=SystemRoleCode.ACTIVITY_SCANNER, granted_by=self.owner)
        local_b = grant_activity_role(profile=self.member, activity=self.activity_b, role=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER, granted_by=self.owner)
        other_local = grant_activity_role(profile=self.member, activity=self.other_activity, role=SystemRoleCode.ACTIVITY_SCANNER, granted_by=self.owner)
        other_space_mandate = grant_space_role(profile=self.member, space=self.other_space, role=SystemRoleCode.FINANCE, granted_by=self.owner)

        remove_member_from_space(membership=self.membership, actor=self.owner)
        self.membership.refresh_from_db()
        local_a.refresh_from_db()
        local_b.refresh_from_db()
        other_local.refresh_from_db()
        other_space_mandate.refresh_from_db()
        self.assertEqual(self.membership.status, TeamMembershipStatus.INACTIVE)
        self.assertFalse(Mandate.objects.filter(profile=self.member, scope_type=AuthorityScope.SPACE, space=self.space, status=MandateStatus.ACTIVE).exists())
        self.assertEqual(local_a.status, MandateStatus.REVOKED)
        self.assertEqual(local_b.status, MandateStatus.REVOKED)
        self.assertEqual(other_local.status, MandateStatus.ACTIVE)
        self.assertEqual(other_space_mandate.status, MandateStatus.ACTIVE)
        self.assertFalse(OrganizationMembership.objects.get(organization=self.space, user=self.member).is_active)

    def test_task18_manual_access_follows_activity_manager_mandate(self):
        with self.assertRaises(PermissionDenied):
            grant_access_manually(actor=self.member, beneficiary=self.beneficiary, activity=self.activity_a)
        mandate = grant_member_activity_responsibility(
            membership=self.membership,
            actor=self.owner,
            activity=self.activity_a,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
        )
        access = grant_access_manually(actor=self.member, beneficiary=self.beneficiary, activity=self.activity_a)
        self.assertEqual(access.activity_id, self.activity_a.pk)
        revoke_member_activity_responsibility(membership=self.membership, actor=self.owner, mandate=mandate)
        with self.assertRaises(PermissionDenied):
            grant_access_manually(actor=self.member, beneficiary=self.beneficiary, activity=self.activity_a)

    def test_expired_activity_mandate_not_shown_as_current_responsibility(self):
        role = Role.objects.get(code=SystemRoleCode.ACTIVITY_SCANNER, scope_type=AuthorityScope.ACTIVITY, is_system=True)
        Mandate.objects.create(
            profile=self.member,
            role=role,
            scope_type=AuthorityScope.ACTIVITY,
            activity=self.activity_a,
            status=MandateStatus.ACTIVE,
            valid_from=timezone.now() - timedelta(days=2),
            valid_until=timezone.now() - timedelta(days=1),
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("organizations:console-team", kwargs={"slug": self.space.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Activity A — Agent de contrôle d’accès")

    def test_membership_idor_and_activity_post_idor_are_blocked(self):
        foreign_member = User.objects.create_user(username="task19-foreign", email="task19-foreign@example.test", password="StrongPass2026!")
        foreign_membership = add_or_update_member(organization=self.other_space, actor=self.owner, user=foreign_member, role=SystemRoleCode.FINANCE)
        self.client.force_login(self.owner)
        foreign_url = reverse("organizations:member-responsibilities", kwargs={"slug": self.space.slug, "membership_id": foreign_membership.pk})
        self.assertEqual(self.client.get(foreign_url).status_code, 404)

        url = reverse("organizations:member-responsibilities", kwargs={"slug": self.space.slug, "membership_id": self.membership.pk})
        response = self.client.post(
            url,
            {"action": "activity-add", "activity": str(self.other_activity.pk), "role": SystemRoleCode.ACTIVITY_SCANNER},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Mandate.objects.filter(profile=self.member, activity=self.other_activity, role__code=SystemRoleCode.ACTIVITY_SCANNER, status=MandateStatus.ACTIVE).exists())
