from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.services import can

from .models import TeamMembership
from .services import add_or_update_member, create_organization
from .team_responsibilities import remove_member_from_space, update_member_space_responsibility


User = get_user_model()


class Task19AuditRegressionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="task19-audit-owner",
            email="task19-audit-owner@example.test",
            password="StrongPass2026!",
        )
        self.admin = User.objects.create_user(
            username="task19-audit-admin",
            email="task19-audit-admin@example.test",
            password="StrongPass2026!",
        )
        self.activity_manager = User.objects.create_user(
            username="task19-audit-activity-manager",
            email="task19-audit-activity-manager@example.test",
            password="StrongPass2026!",
        )
        self.member = User.objects.create_user(
            username="task19-audit-member",
            email="task19-audit-member@example.test",
            password="StrongPass2026!",
        )
        self.external = User.objects.create_user(
            username="task19-audit-external",
            email="task19-audit-external@example.test",
            password="StrongPass2026!",
        )
        self.space = create_organization(creator=self.owner, name="Task 19 Audit Space")
        add_or_update_member(
            organization=self.space,
            actor=self.owner,
            user=self.admin,
            role=SystemRoleCode.SPACE_ADMIN,
        )
        add_or_update_member(
            organization=self.space,
            actor=self.owner,
            user=self.activity_manager,
            role=SystemRoleCode.ACTIVITY_MANAGER,
        )
        self.membership = add_or_update_member(
            organization=self.space,
            actor=self.owner,
            user=self.member,
            role=SystemRoleCode.FINANCE,
        )

    def test_admin_with_team_manage_can_update_regular_member_responsibility(self):
        self.assertTrue(can(self.admin, PermissionCode.SPACE_TEAM_MANAGE, self.space))

        update_member_space_responsibility(
            membership=self.membership,
            actor=self.admin,
            role_code=SystemRoleCode.MARKETING,
        )

        self.assertFalse(can(self.member, PermissionCode.FINANCE_VIEW, self.space))
        self.assertTrue(can(self.member, PermissionCode.MARKETING_MANAGE, self.space))

    def test_space_activity_manager_does_not_gain_team_management(self):
        self.assertFalse(can(self.activity_manager, PermissionCode.SPACE_TEAM_MANAGE, self.space))
        self.client.force_login(self.activity_manager)

        team_url = reverse("organizations:console-team", kwargs={"slug": self.space.slug})
        responsibilities_url = reverse(
            "organizations:member-responsibilities",
            kwargs={"slug": self.space.slug, "membership_id": self.membership.pk},
        )

        self.assertEqual(self.client.get(team_url).status_code, 403)
        self.assertEqual(self.client.get(responsibilities_url).status_code, 403)

    def test_external_authenticated_user_cannot_view_or_mutate_member_responsibilities(self):
        self.client.force_login(self.external)
        url = reverse(
            "organizations:member-responsibilities",
            kwargs={"slug": self.space.slug, "membership_id": self.membership.pk},
        )

        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.post(
            url,
            {"action": "space-role", "role": SystemRoleCode.SPACE_ADMIN},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(can(self.member, PermissionCode.SPACE_MANAGE, self.space))
        self.assertTrue(can(self.member, PermissionCode.FINANCE_VIEW, self.space))

    def test_last_owner_cannot_be_removed_from_team(self):
        owner_membership = TeamMembership.objects.get(
            team__organization=self.space,
            user=self.owner,
        )

        with self.assertRaises(ValidationError):
            remove_member_from_space(membership=owner_membership, actor=self.owner)

        owner_membership.refresh_from_db()
        self.assertTrue(owner_membership.is_active)
        self.assertTrue(can(self.owner, PermissionCode.SPACE_OWNERSHIP_MANAGE, self.space))
