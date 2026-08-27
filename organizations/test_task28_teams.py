from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import Mandate, MandateStatus
from authorization.services import can

from .console_context import SpaceConsoleContext
from .models import TeamMembership, TeamMembershipStatus
from .services import (
    add_existing_collaborator_to_team,
    add_or_update_member,
    archive_team,
    create_organization,
    create_team,
    remove_member_from_team,
    rename_team,
)
from .team_responsibilities import remove_member_from_space


User = get_user_model()


class Task28TeamLifecycleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="task28-owner",
            email="task28-owner@example.test",
            password="StrongPass2026!",
        )
        self.member = User.objects.create_user(
            username="task28-member",
            email="task28-member@example.test",
            password="StrongPass2026!",
        )
        self.outsider = User.objects.create_user(
            username="task28-outsider",
            email="task28-outsider@example.test",
            password="StrongPass2026!",
        )
        self.space = create_organization(creator=self.owner, name="Task 28 Mulykap")
        self.other_space = create_organization(creator=self.owner, name="Task 28 Other Space")
        self.primary_membership = add_or_update_member(
            organization=self.space,
            actor=self.owner,
            user=self.member,
            role=SystemRoleCode.FINANCE,
        )
        self.other_primary_membership = add_or_update_member(
            organization=self.other_space,
            actor=self.owner,
            user=self.member,
            role=SystemRoleCode.MARKETING,
        )

    def test_space_supports_multiple_secondary_teams_without_duplicate_profile_or_mandate(self):
        finance = create_team(organization=self.space, actor=self.owner, name="Finance")
        operations = create_team(organization=self.space, actor=self.owner, name="Opérations")
        mandate_count = Mandate.objects.filter(
            profile=self.member,
            space=self.space,
            status=MandateStatus.ACTIVE,
        ).count()

        finance_membership = add_existing_collaborator_to_team(
            team=finance,
            actor=self.owner,
            user=self.member,
        )
        operations_membership = add_existing_collaborator_to_team(
            team=operations,
            actor=self.owner,
            user=self.member,
        )

        self.assertEqual(
            TeamMembership.objects.filter(
                team__organization=self.space,
                user=self.member,
                status=TeamMembershipStatus.ACTIVE,
            ).count(),
            3,
        )
        self.assertEqual(finance_membership.user_id, self.member.pk)
        self.assertEqual(operations_membership.user_id, self.member.pk)
        self.assertEqual(
            Mandate.objects.filter(
                profile=self.member,
                space=self.space,
                status=MandateStatus.ACTIVE,
            ).count(),
            mandate_count,
        )
        self.assertTrue(can(self.member, PermissionCode.FINANCE_VIEW, self.space))

    def test_same_team_name_is_unique_per_space_but_allowed_across_spaces(self):
        create_team(organization=self.space, actor=self.owner, name="  Finance   Terrain  ")
        other = create_team(organization=self.other_space, actor=self.owner, name="Finance Terrain")
        self.assertEqual(other.name, "Finance Terrain")
        with self.assertRaises(ValidationError):
            create_team(organization=self.space, actor=self.owner, name="Finance Terrain")

    def test_secondary_team_can_be_renamed_and_archived_but_default_cannot_be_archived(self):
        team = create_team(organization=self.space, actor=self.owner, name="Accueil")
        original_pk = team.pk
        rename_team(team=team, actor=self.owner, name="Accueil terrain")
        team.refresh_from_db()
        self.assertEqual(team.pk, original_pk)
        self.assertEqual(team.name, "Accueil terrain")

        archive_team(team=team, actor=self.owner)
        team.refresh_from_db()
        self.assertFalse(team.is_active)

        default_team = self.space.teams.get(is_default=True)
        with self.assertRaises(ValidationError):
            archive_team(team=default_team, actor=self.owner)
        default_team.refresh_from_db()
        self.assertTrue(default_team.is_active)

    def test_remove_from_secondary_team_preserves_space_other_team_and_mandates(self):
        finance = create_team(organization=self.space, actor=self.owner, name="Finance terrain")
        operations = create_team(organization=self.space, actor=self.owner, name="Opérations terrain")
        finance_membership = add_existing_collaborator_to_team(team=finance, actor=self.owner, user=self.member)
        operations_membership = add_existing_collaborator_to_team(team=operations, actor=self.owner, user=self.member)

        remove_member_from_team(membership=finance_membership, actor=self.owner)
        finance_membership.refresh_from_db()
        operations_membership.refresh_from_db()
        self.primary_membership.refresh_from_db()

        self.assertEqual(finance_membership.status, TeamMembershipStatus.INACTIVE)
        self.assertEqual(operations_membership.status, TeamMembershipStatus.ACTIVE)
        self.assertEqual(self.primary_membership.status, TeamMembershipStatus.ACTIVE)
        self.assertTrue(can(self.member, PermissionCode.FINANCE_VIEW, self.space))

    def test_remove_from_space_deactivates_every_local_team_but_not_other_space(self):
        finance = create_team(organization=self.space, actor=self.owner, name="Finance terrain")
        operations = create_team(organization=self.space, actor=self.owner, name="Opérations terrain")
        add_existing_collaborator_to_team(team=finance, actor=self.owner, user=self.member)
        add_existing_collaborator_to_team(team=operations, actor=self.owner, user=self.member)
        other_team = create_team(organization=self.other_space, actor=self.owner, name="Communication")
        other_membership = add_existing_collaborator_to_team(
            team=other_team,
            actor=self.owner,
            user=self.member,
        )

        remove_member_from_space(membership=self.primary_membership, actor=self.owner)

        self.assertFalse(
            TeamMembership.objects.filter(
                team__organization=self.space,
                user=self.member,
                status=TeamMembershipStatus.ACTIVE,
            ).exists()
        )
        other_membership.refresh_from_db()
        self.assertEqual(other_membership.status, TeamMembershipStatus.ACTIVE)
        self.other_primary_membership.refresh_from_db()
        self.assertEqual(self.other_primary_membership.status, TeamMembershipStatus.ACTIVE)
        self.assertFalse(can(self.member, PermissionCode.FINANCE_VIEW, self.space))
        self.assertTrue(can(self.member, PermissionCode.MARKETING_MANAGE, self.other_space))

    def test_team_membership_alone_does_not_open_space_console(self):
        TeamMembership.objects.create(
            team=self.space.teams.get(is_default=True),
            user=self.outsider,
            status=TeamMembershipStatus.ACTIVE,
            joined_at=timezone.now(),
        )
        self.assertIsNone(SpaceConsoleContext.build(self.outsider, self.space))
        self.assertFalse(can(self.outsider, PermissionCode.SPACE_VIEW, self.space))

    def test_team_mutations_require_space_team_permission(self):
        with self.assertRaises(PermissionDenied):
            create_team(organization=self.space, actor=self.outsider, name="Forged")

    def test_team_route_rejects_team_uuid_from_another_space(self):
        foreign_team = create_team(
            organization=self.other_space,
            actor=self.owner,
            name="Foreign Team",
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "organizations:team-rename",
                kwargs={"slug": self.space.slug, "team_id": foreign_team.pk},
            )
        )
        self.assertEqual(response.status_code, 404)
