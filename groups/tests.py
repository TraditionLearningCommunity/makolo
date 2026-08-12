from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, MandateStatus, Role
from authorization.services import can, grant_group_role, revoke_mandate
from organizations.models import TeamMembership, TeamMembershipStatus
from organizations.services import create_organization

from .models import (
    Group,
    GroupInvitation,
    GroupInvitationStatus,
    GroupMembership,
    GroupMembershipSource,
    GroupMembershipStatus,
    GroupSnapshot,
    GroupSnapshotMember,
    GroupStatus,
    GroupVisibility,
)
from .services import (
    accept_invitation,
    add_member,
    archive_group,
    assign_group_responsibility,
    create_group,
    create_snapshot,
    has_group_permission,
    import_group_csv,
    invite_member,
    leave_group,
    link_invitation_profile,
    parse_group_csv,
    remove_member,
    revoke_invitation,
    suspend_member,
    transfer_personal_group_ownership,
)


User = get_user_model()
PASSWORD = "Password123!"


def csv_upload(text, name="group.csv"):
    return SimpleUploadedFile(name, text.encode("utf-8"), content_type="text/csv")


class GroupTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="group-owner",
            email="group-owner@example.com",
            password=PASSWORD,
        )
        cls.member = User.objects.create_user(
            username="group-member",
            email="group-member@example.com",
            password=PASSWORD,
            phone="+243999000001",
        )
        cls.other = User.objects.create_user(
            username="group-other",
            email="group-other@example.com",
            password=PASSWORD,
            phone="+243999000002",
        )
        cls.space_owner = User.objects.create_user(
            username="space-owner-groups",
            email="space-owner-groups@example.com",
            password=PASSWORD,
        )
        cls.other_space_owner = User.objects.create_user(
            username="space-owner-other",
            email="space-owner-other@example.com",
            password=PASSWORD,
        )
        cls.team_only = User.objects.create_user(
            username="team-only",
            email="team-only@example.com",
            password=PASSWORD,
        )
        cls.space = create_organization(creator=cls.space_owner, name="Mulykap Group Tests")
        cls.other_space = create_organization(
            creator=cls.other_space_owner,
            name="Autre Espace Group Tests",
        )
        TeamMembership.objects.create(
            team=cls.space.primary_team,
            user=cls.team_only,
            status=TeamMembershipStatus.ACTIVE,
            invited_by=cls.space_owner,
        )

    def personal_group(self, owner=None, name="Promotion Informatique 2026"):
        return create_group(actor=owner or self.owner, name=name)

    def space_group(self, space=None, actor=None, name="Employés Mulykap"):
        return create_group(
            actor=actor or self.space_owner,
            name=name,
            space=space or self.space,
            visibility=GroupVisibility.SPACE,
        )


class GroupModelAndOwnershipTests(GroupTestBase):
    def test_personal_group_has_profile_owner_and_owner_mandate(self):
        group = self.personal_group()
        self.assertEqual(group.owner_profile, self.owner)
        self.assertIsNone(group.space)
        self.assertTrue(can(self.owner, PermissionCode.GROUP_MANAGE, group=group))
        self.assertTrue(
            Mandate.objects.filter(
                profile=self.owner,
                group=group,
                role__code=SystemRoleCode.GROUP_OWNER,
                status=MandateStatus.ACTIVE,
            ).exists()
        )

    def test_space_group_has_space_owner_only(self):
        group = self.space_group()
        self.assertEqual(group.space, self.space)
        self.assertIsNone(group.owner_profile)
        self.assertFalse(
            Mandate.objects.filter(group=group, role__code=SystemRoleCode.GROUP_OWNER).exists()
        )

    def test_group_rejects_missing_logical_owner(self):
        group = Group(name="Sans propriétaire")
        with self.assertRaises(ValidationError):
            group.full_clean()

    def test_group_rejects_both_logical_owners(self):
        group = Group(name="Double", space=self.space, owner_profile=self.owner)
        with self.assertRaises(ValidationError):
            group.full_clean()

    def test_database_enforces_exactly_one_owner(self):
        with self.assertRaises(IntegrityError):
            Group.objects.create(name="DB invalid", slug="db-invalid")

    def test_archive_is_idempotent(self):
        group = self.personal_group()
        first = archive_group(actor=self.owner, group=group)
        second = archive_group(actor=self.owner, group=first)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Group.objects.get(pk=group.pk).status, GroupStatus.ARCHIVED)

    def test_transfer_personal_ownership_moves_owner_mandate(self):
        group = self.personal_group()
        transfer_personal_group_ownership(actor=self.owner, group=group, new_owner=self.other)
        group.refresh_from_db()
        self.assertEqual(group.owner_profile, self.other)
        self.assertTrue(can(self.other, PermissionCode.GROUP_OWNERSHIP_MANAGE, group=group))
        self.assertFalse(can(self.owner, PermissionCode.GROUP_OWNERSHIP_MANAGE, group=group))

    def test_last_personal_owner_mandate_cannot_be_revoked(self):
        group = self.personal_group()
        mandate = Mandate.objects.get(
            group=group,
            profile=self.owner,
            role__code=SystemRoleCode.GROUP_OWNER,
            status=MandateStatus.ACTIVE,
        )
        with self.assertRaises(ValidationError):
            revoke_mandate(mandate=mandate, actor=self.owner)


class GroupMembershipTests(GroupTestBase):
    def setUp(self):
        self.group = self.personal_group()

    def test_add_member(self):
        membership, created = add_member(actor=self.owner, group=self.group, profile=self.member)
        self.assertTrue(created)
        self.assertEqual(membership.status, GroupMembershipStatus.ACTIVE)

    def test_add_member_duplicate_is_idempotent(self):
        add_member(actor=self.owner, group=self.group, profile=self.member)
        _, created = add_member(actor=self.owner, group=self.group, profile=self.member)
        self.assertFalse(created)
        self.assertEqual(GroupMembership.objects.filter(group=self.group, profile=self.member).count(), 1)

    def test_external_reference_unique_inside_group(self):
        add_member(actor=self.owner, group=self.group, profile=self.member, external_reference="INFO-2026-184")
        with self.assertRaises(ValidationError):
            add_member(actor=self.owner, group=self.group, profile=self.other, external_reference="INFO-2026-184")

    def test_same_external_reference_allowed_in_other_group(self):
        other_group = self.personal_group(name="Autre promotion")
        add_member(actor=self.owner, group=self.group, profile=self.member, external_reference="184")
        membership, _ = add_member(actor=self.owner, group=other_group, profile=self.other, external_reference="184")
        self.assertEqual(membership.external_reference, "184")

    def test_suspend_member_preserves_history(self):
        membership, _ = add_member(actor=self.owner, group=self.group, profile=self.member)
        suspend_member(actor=self.owner, group=self.group, profile=self.member)
        membership.refresh_from_db()
        self.assertEqual(membership.status, GroupMembershipStatus.SUSPENDED)

    def test_remove_member_preserves_history(self):
        membership, _ = add_member(actor=self.owner, group=self.group, profile=self.member)
        remove_member(actor=self.owner, group=self.group, profile=self.member)
        membership.refresh_from_db()
        self.assertEqual(membership.status, GroupMembershipStatus.REMOVED)
        self.assertTrue(GroupMembership.objects.filter(pk=membership.pk).exists())

    def test_member_can_leave(self):
        membership, _ = add_member(actor=self.owner, group=self.group, profile=self.member)
        leave_group(profile=self.member, group=self.group)
        membership.refresh_from_db()
        self.assertEqual(membership.status, GroupMembershipStatus.LEFT)

    def test_membership_never_grants_admin_authority(self):
        add_member(actor=self.owner, group=self.group, profile=self.member)
        self.assertFalse(has_group_permission(self.member, PermissionCode.GROUP_MANAGE, self.group))
        self.assertFalse(has_group_permission(self.member, PermissionCode.GROUP_MEMBERS_MANAGE, self.group))


class GroupMandateAndInheritanceTests(GroupTestBase):
    def setUp(self):
        self.group_a = self.personal_group(name="Groupe A")
        self.group_b = self.personal_group(name="Groupe B")

    def test_group_admin_can_manage_only_target_group(self):
        grant_group_role(profile=self.member, group=self.group_a, role=SystemRoleCode.GROUP_ADMIN, granted_by=self.owner)
        self.assertTrue(can(self.member, PermissionCode.GROUP_MANAGE, group=self.group_a))
        self.assertFalse(can(self.member, PermissionCode.GROUP_MANAGE, group=self.group_b))

    def test_group_moderator_manages_members_not_group(self):
        grant_group_role(profile=self.member, group=self.group_a, role=SystemRoleCode.GROUP_MODERATOR, granted_by=self.owner)
        self.assertTrue(can(self.member, PermissionCode.GROUP_MEMBERS_MANAGE, group=self.group_a))
        self.assertFalse(can(self.member, PermissionCode.GROUP_MANAGE, group=self.group_a))
        self.assertFalse(can(self.member, PermissionCode.FINANCE_MANAGE, self.space))

    def test_expired_group_mandate_is_ignored(self):
        mandate = grant_group_role(profile=self.member, group=self.group_a, role=SystemRoleCode.GROUP_ADMIN, granted_by=self.owner)
        mandate.valid_until = timezone.now() - timedelta(seconds=1)
        mandate.save(update_fields=["valid_until", "updated_at"])
        self.assertFalse(can(self.member, PermissionCode.GROUP_MANAGE, group=self.group_a))

    def test_revoked_group_mandate_is_ignored(self):
        mandate = grant_group_role(profile=self.member, group=self.group_a, role=SystemRoleCode.GROUP_ADMIN, granted_by=self.owner)
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertFalse(can(self.member, PermissionCode.GROUP_MANAGE, group=self.group_a))

    def test_inactive_group_role_is_ignored(self):
        role = Role.objects.get(code=SystemRoleCode.GROUP_ADMIN, is_system=True)
        mandate = grant_group_role(profile=self.member, group=self.group_a, role=role, granted_by=self.owner)
        role.is_active = False
        role.save(update_fields=["is_active", "updated_at"])
        self.assertFalse(can(self.member, PermissionCode.GROUP_MANAGE, group=self.group_a))
        self.assertEqual(mandate.group, self.group_a)

    def test_group_admin_has_no_space_authority(self):
        grant_group_role(profile=self.member, group=self.group_a, role=SystemRoleCode.GROUP_ADMIN, granted_by=self.owner)
        self.assertFalse(can(self.member, PermissionCode.SPACE_MANAGE, self.space))
        self.assertFalse(can(self.member, PermissionCode.FINANCE_VIEW, self.space))

    def test_space_admin_permission_inherits_to_its_group(self):
        group = self.space_group()
        self.assertTrue(has_group_permission(self.space_owner, PermissionCode.GROUP_MANAGE, group))
        self.assertTrue(has_group_permission(self.space_owner, PermissionCode.GROUP_MEMBERS_MANAGE, group))

    def test_space_admin_cannot_manage_other_space_group(self):
        foreign = self.space_group(space=self.other_space, actor=self.other_space_owner, name="Autre groupe")
        self.assertFalse(has_group_permission(self.space_owner, PermissionCode.GROUP_MANAGE, foreign))

    def test_team_membership_without_permission_cannot_manage_space_group(self):
        group = self.space_group()
        self.assertFalse(has_group_permission(self.team_only, PermissionCode.GROUP_MANAGE, group))

    def test_group_responsibility_assignment_uses_mandate(self):
        mandate = assign_group_responsibility(
            actor=self.owner,
            group=self.group_a,
            profile=self.member,
            role_code=SystemRoleCode.GROUP_MODERATOR,
        )
        self.assertEqual(mandate.scope_type, AuthorityScope.GROUP)
        self.assertEqual(mandate.group, self.group_a)
        self.assertIsNone(mandate.space)


class GroupInvitationTests(GroupTestBase):
    def setUp(self):
        self.group = self.personal_group()

    def test_create_invitation_stores_digest_not_raw_token(self):
        invitation, token = invite_member(actor=self.owner, group=self.group, email=self.member.email)
        self.assertNotEqual(invitation.token_digest, token)
        self.assertEqual(len(invitation.token_digest), 64)
        self.assertEqual(invitation.profile, self.member)

    def test_good_profile_accepts_invitation_once(self):
        invitation, token = invite_member(actor=self.owner, group=self.group, email=self.member.email)
        accepted, membership = accept_invitation(profile=self.member, token=token)
        self.assertEqual(accepted.status, GroupInvitationStatus.ACCEPTED)
        self.assertEqual(membership.status, GroupMembershipStatus.ACTIVE)
        with self.assertRaises(ValidationError):
            accept_invitation(profile=self.member, token=token)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, GroupInvitationStatus.ACCEPTED)

    def test_transferred_token_cannot_add_wrong_profile(self):
        _, token = invite_member(actor=self.owner, group=self.group, email=self.member.email)
        with self.assertRaises(PermissionDenied):
            accept_invitation(profile=self.other, token=token)
        self.assertFalse(GroupMembership.objects.filter(group=self.group, profile=self.other).exists())

    def test_expired_invitation_is_rejected(self):
        invitation, token = invite_member(actor=self.owner, group=self.group, email=self.member.email)
        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save(update_fields=["expires_at", "updated_at"])
        with self.assertRaises(ValidationError):
            accept_invitation(profile=self.member, token=token)

    def test_revoked_invitation_is_unusable(self):
        invitation, token = invite_member(actor=self.owner, group=self.group, email=self.member.email)
        revoke_invitation(actor=self.owner, invitation=invitation)
        with self.assertRaises(ValidationError):
            accept_invitation(profile=self.member, token=token)

    def test_external_reference_only_cannot_self_claim(self):
        _, token = invite_member(
            actor=self.owner,
            group=self.group,
            external_reference="INFO-2026-184",
        )
        with self.assertRaises(PermissionDenied):
            accept_invitation(profile=self.member, token=token)

    def test_external_reference_invitation_can_be_linked_by_admin(self):
        invitation, token = invite_member(
            actor=self.owner,
            group=self.group,
            external_reference="INFO-2026-184",
        )
        link_invitation_profile(actor=self.owner, invitation=invitation, profile=self.member)
        _, membership = accept_invitation(profile=self.member, token=token)
        self.assertEqual(membership.external_reference, "INFO-2026-184")

    def test_phone_only_requires_verified_phone_for_claim(self):
        _, token = invite_member(actor=self.owner, group=self.group, phone=self.member.phone)
        self.member.phone_verified = False
        self.member.save(update_fields=["phone_verified", "updated_at"])
        with self.assertRaises(PermissionDenied):
            accept_invitation(profile=self.member, token=token)


class GroupImportTests(GroupTestBase):
    def setUp(self):
        self.group = self.personal_group()

    def test_import_200_existing_profiles(self):
        users = [
            User(
                username=f"bulk-{index}",
                email=f"bulk-{index}@example.com",
                password="!",
                is_active=True,
            )
            for index in range(200)
        ]
        User.objects.bulk_create(users)
        csv_text = "email,external_reference\n" + "\n".join(
            f"bulk-{index}@example.com,INFO-{index:03d}" for index in range(200)
        )
        result = import_group_csv(actor=self.owner, group=self.group, upload=csv_upload(csv_text))
        self.assertEqual(result.members_added, 200)
        self.assertEqual(result.invitations_created, 0)
        self.assertEqual(GroupMembership.objects.filter(group=self.group).count(), 200)

    def test_unknown_user_creates_invitation_not_profile(self):
        result = import_group_csv(
            actor=self.owner,
            group=self.group,
            upload=csv_upload("email,external_reference\nabsent@example.com,EXT-1\n"),
        )
        self.assertEqual(result.invitations_created, 1)
        self.assertFalse(User.objects.filter(email="absent@example.com").exists())
        self.assertTrue(GroupInvitation.objects.filter(group=self.group, email="absent@example.com").exists())

    def test_duplicate_rows_are_reported_before_writes(self):
        rows, result = parse_group_csv(
            csv_upload("email,external_reference\na@example.com,1\na@example.com,1\n")
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(result.duplicates_ignored, 1)

    def test_contradictory_rows_are_reported(self):
        rows, result = parse_group_csv(
            csv_upload("email,external_reference\na@example.com,1\na@example.com,2\n")
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(result.conflicts, 1)

    def test_bad_csv_header_is_rejected(self):
        with self.assertRaises(ValidationError):
            parse_group_csv(csv_upload("name\nAlice\n"))

    def test_existing_profile_is_added_with_import_source(self):
        result = import_group_csv(
            actor=self.owner,
            group=self.group,
            upload=csv_upload(f"email,external_reference\n{self.member.email},MAT-1\n"),
        )
        membership = GroupMembership.objects.get(group=self.group, profile=self.member)
        self.assertEqual(result.members_added, 1)
        self.assertEqual(membership.source, GroupMembershipSource.IMPORT)
        self.assertEqual(membership.external_reference, "MAT-1")

    def test_email_phone_conflict_is_not_guessed(self):
        result = import_group_csv(
            actor=self.owner,
            group=self.group,
            upload=csv_upload(
                f"email,phone,external_reference\n{self.member.email},{self.other.phone},CONFLICT\n"
            ),
        )
        self.assertEqual(result.conflicts, 1)
        self.assertEqual(result.members_added, 0)
        self.assertEqual(result.invitations_created, 0)

    def test_repeated_import_does_not_duplicate_membership(self):
        content = f"email,external_reference\n{self.member.email},MAT-REPEAT\n"
        first = import_group_csv(actor=self.owner, group=self.group, upload=csv_upload(content))
        second = import_group_csv(actor=self.owner, group=self.group, upload=csv_upload(content))
        self.assertEqual(first.members_added, 1)
        self.assertEqual(second.duplicates_ignored, 1)
        self.assertEqual(GroupMembership.objects.filter(group=self.group, profile=self.member).count(), 1)

    def test_repeated_unknown_import_does_not_duplicate_invitation(self):
        content = "email,external_reference\nnewperson@example.com,NEW-1\n"
        first = import_group_csv(actor=self.owner, group=self.group, upload=csv_upload(content))
        second = import_group_csv(actor=self.owner, group=self.group, upload=csv_upload(content))
        self.assertEqual(first.invitations_created, 1)
        self.assertEqual(second.duplicates_ignored, 1)
        self.assertEqual(GroupInvitation.objects.filter(group=self.group, email="newperson@example.com").count(), 1)

    def test_import_rejects_more_than_1000_rows(self):
        text = "email\n" + "\n".join(f"person-{index}@example.com" for index in range(1001))
        with self.assertRaises(ValidationError):
            parse_group_csv(csv_upload(text))


class GroupSnapshotTests(GroupTestBase):
    def setUp(self):
        self.group = self.personal_group()

    def test_snapshot_contains_only_active_members(self):
        add_member(actor=self.owner, group=self.group, profile=self.member)
        add_member(actor=self.owner, group=self.group, profile=self.other)
        suspend_member(actor=self.owner, group=self.group, profile=self.other)
        snapshot = create_snapshot(actor=self.owner, group=self.group, name="Population initiale")
        self.assertEqual(snapshot.member_count, 1)
        self.assertEqual(list(snapshot.members.values_list("profile_id", flat=True)), [self.member.pk])

    def test_new_members_after_snapshot_are_absent(self):
        add_member(actor=self.owner, group=self.group, profile=self.member)
        snapshot = create_snapshot(actor=self.owner, group=self.group)
        add_member(actor=self.owner, group=self.group, profile=self.other)
        self.assertFalse(snapshot.members.filter(profile=self.other).exists())

    def test_removed_member_remains_in_historical_snapshot(self):
        add_member(actor=self.owner, group=self.group, profile=self.member)
        snapshot = create_snapshot(actor=self.owner, group=self.group)
        remove_member(actor=self.owner, group=self.group, profile=self.member)
        self.assertTrue(snapshot.members.filter(profile=self.member).exists())

    def test_snapshot_is_immutable(self):
        snapshot = create_snapshot(actor=self.owner, group=self.group, name="Immuable")
        snapshot.name = "Altéré"
        with self.assertRaises(ValidationError):
            snapshot.save()

    def test_snapshot_member_is_immutable(self):
        add_member(actor=self.owner, group=self.group, profile=self.member)
        snapshot = create_snapshot(actor=self.owner, group=self.group)
        member = GroupSnapshotMember.objects.get(snapshot=snapshot, profile=self.member)
        member.external_reference = "CHANGED"
        with self.assertRaises(ValidationError):
            member.save()


class GroupWebPermissionTests(GroupTestBase):
    def setUp(self):
        self.group = self.personal_group()
        add_member(actor=self.owner, group=self.group, profile=self.member)

    def test_member_sees_group_detail_without_admin_controls(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("groups:detail", kwargs={"slug": self.group.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.group.name)
        self.assertNotContains(response, "Administrer")

    def test_member_direct_members_admin_route_is_403(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("groups:members", kwargs={"slug": self.group.slug}))
        self.assertEqual(response.status_code, 403)

    def test_group_a_admin_cannot_manage_group_b(self):
        group_b = self.personal_group(name="Isolation B")
        grant_group_role(profile=self.member, group=self.group, role=SystemRoleCode.GROUP_ADMIN, granted_by=self.owner)
        self.client.force_login(self.member)
        response = self.client.get(reverse("groups:members", kwargs={"slug": group_b.slug}))
        self.assertEqual(response.status_code, 403)

    def test_members_page_does_not_exist_for_anonymous_user(self):
        response = self.client.get(reverse("groups:members", kwargs={"slug": self.group.slug}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_invitation_page_hides_group_before_authentication(self):
        _, token = invite_member(actor=self.owner, group=self.group, email=self.member.email)
        response = self.client.get(reverse("groups:invitation", kwargs={"token": token}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.group.name)
        self.assertContains(response, "Créer un compte")
