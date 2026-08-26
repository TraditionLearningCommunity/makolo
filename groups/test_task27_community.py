from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from activities.models import ActivityStatus
from activities.services import create_activity
from authorization.constants import PermissionCode
from groups.community_group_services import create_community_group
from groups.community_selectors import discoverable_groups
from groups.community_services import (
    approve_join_request,
    decide_activity_group_eligibility,
    join_group,
    profile_is_eligible_for_activity,
    request_activity_group_eligibility,
    request_to_join,
)
from groups.models import (
    ActivityGroupEligibilityStatus,
    Group,
    GroupDiscoverability,
    GroupJoinRequest,
    GroupJoinRequestStatus,
    GroupMembership,
    GroupMembershipPolicy,
    GroupMembershipStatus,
)
from groups.services import add_member, has_group_permission, remove_member, suspend_member
from journeys.models import WorkflowKind
from journeys.services import create_journey


User = get_user_model()
PASSWORD = "Password123!"


class Task27CommunityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.christophe = User.objects.create_user(
            username="t27-christophe",
            email="t27-christophe@example.com",
            password=PASSWORD,
        )
        cls.sarah = User.objects.create_user(
            username="t27-sarah",
            email="t27-sarah@example.com",
            password=PASSWORD,
        )
        cls.member = User.objects.create_user(
            username="t27-member",
            email="t27-member@example.com",
            password=PASSWORD,
        )
        cls.outsider = User.objects.create_user(
            username="t27-outsider",
            email="t27-outsider@example.com",
            password=PASSWORD,
        )

    def group(self, *, discoverability=GroupDiscoverability.LISTED, policy=GroupMembershipPolicy.REQUEST):
        return create_community_group(
            actor=self.christophe,
            name=f"MAPENDO {Group.objects.count()}",
            discoverability=discoverability,
            membership_policy=policy,
        )

    def test_listed_is_searchable_but_unlisted_and_hidden_are_not(self):
        listed = self.group(discoverability=GroupDiscoverability.LISTED)
        self.group(discoverability=GroupDiscoverability.UNLISTED)
        self.group(discoverability=GroupDiscoverability.HIDDEN)
        result = list(discoverable_groups(profile=self.outsider, query="MAPENDO"))
        self.assertEqual(result, [listed])

    def test_hidden_group_returns_404_to_unauthorized_profile(self):
        hidden = self.group(
            discoverability=GroupDiscoverability.HIDDEN,
            policy=GroupMembershipPolicy.INVITE_ONLY,
        )
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("groups:detail", kwargs={"slug": hidden.slug}))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, hidden.name, status_code=404)

    def test_unlisted_group_is_available_by_direct_link(self):
        group = self.group(discoverability=GroupDiscoverability.UNLISTED)
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("groups:detail", kwargs={"slug": group.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, group.name)

    def test_open_join_is_active_and_idempotent(self):
        group = self.group(policy=GroupMembershipPolicy.OPEN)
        membership, created = join_group(profile=self.member, group=group)
        again, created_again = join_group(profile=self.member, group=group)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(membership.pk, again.pk)
        self.assertEqual(membership.status, GroupMembershipStatus.ACTIVE)
        self.assertEqual(GroupMembership.objects.filter(group=group, profile=self.member).count(), 1)

    def test_request_does_not_create_membership_before_approval(self):
        group = self.group(policy=GroupMembershipPolicy.REQUEST)
        request, created = request_to_join(profile=self.member, group=group)
        duplicate, created_duplicate = request_to_join(profile=self.member, group=group)
        self.assertTrue(created)
        self.assertFalse(created_duplicate)
        self.assertEqual(request.pk, duplicate.pk)
        self.assertFalse(GroupMembership.objects.filter(group=group, profile=self.member).exists())
        approved, membership = approve_join_request(actor=self.christophe, request=request)
        self.assertEqual(approved.status, GroupJoinRequestStatus.APPROVED)
        self.assertEqual(membership.status, GroupMembershipStatus.ACTIVE)
        self.assertEqual(membership.source, "request")

    def test_invite_only_rejects_direct_join_and_request(self):
        group = self.group(policy=GroupMembershipPolicy.INVITE_ONLY)
        with self.assertRaises(PermissionDenied):
            join_group(profile=self.member, group=group)
        with self.assertRaises(PermissionDenied):
            request_to_join(profile=self.member, group=group)

    def test_left_can_rejoin_open_but_removed_and_suspended_cannot(self):
        group = self.group(policy=GroupMembershipPolicy.OPEN)
        membership, _ = add_member(actor=self.christophe, group=group, profile=self.member)
        membership.status = GroupMembershipStatus.LEFT
        membership.save(update_fields=["status", "updated_at"])
        rejoined, _ = join_group(profile=self.member, group=group)
        self.assertEqual(rejoined.status, GroupMembershipStatus.ACTIVE)
        suspend_member(actor=self.christophe, group=group, profile=self.member)
        with self.assertRaises(PermissionDenied):
            join_group(profile=self.member, group=group)
        membership.status = GroupMembershipStatus.ACTIVE
        membership.save(update_fields=["status", "updated_at"])
        remove_member(actor=self.christophe, group=group, profile=self.member)
        with self.assertRaises(PermissionDenied):
            join_group(profile=self.member, group=group)

    def test_membership_never_grants_group_management(self):
        group = self.group(policy=GroupMembershipPolicy.OPEN)
        join_group(profile=self.member, group=group)
        self.assertFalse(has_group_permission(self.member, PermissionCode.GROUP_MANAGE, group))
        self.assertFalse(has_group_permission(self.member, PermissionCode.GROUP_MEMBERS_MANAGE, group))

    def test_cross_owner_usage_requires_group_consent_and_does_not_clone_group(self):
        group = self.group(policy=GroupMembershipPolicy.REQUEST)
        activity = create_activity(
            created_by=self.sarah,
            owner_profile=self.sarah,
            title="Voyage Alumni",
            status=ActivityStatus.PUBLISHED,
        )
        relation, created = request_activity_group_eligibility(
            actor=self.sarah,
            activity=activity,
            group=group,
        )
        self.assertTrue(created)
        self.assertEqual(relation.status, ActivityGroupEligibilityStatus.REQUESTED)
        self.assertEqual(Group.objects.filter(pk=group.pk).count(), 1)
        decide_activity_group_eligibility(
            actor=self.christophe,
            eligibility=relation,
            approve=True,
        )
        relation.refresh_from_db()
        self.assertEqual(relation.status, ActivityGroupEligibilityStatus.APPROVED)
        self.assertEqual(group.owner_profile, self.christophe)
        self.assertEqual(Group.objects.count(), 1)

    def test_same_manager_on_both_sides_is_approved_immediately(self):
        group = self.group()
        activity = create_activity(
            created_by=self.christophe,
            owner_profile=self.christophe,
            title="Mariage Christophe",
        )
        relation, _ = request_activity_group_eligibility(
            actor=self.christophe,
            activity=activity,
            group=group,
        )
        self.assertEqual(relation.status, ActivityGroupEligibilityStatus.APPROVED)

    def test_forged_group_uuid_cannot_be_attached_by_activity_outsider(self):
        group = self.group()
        activity = create_activity(
            created_by=self.sarah,
            owner_profile=self.sarah,
            title="Activity Sarah",
        )
        with self.assertRaises(PermissionDenied):
            request_activity_group_eligibility(
                actor=self.outsider,
                activity=activity,
                group=group,
            )

    def test_only_active_membership_satisfies_activity_eligibility(self):
        group = self.group(policy=GroupMembershipPolicy.OPEN)
        activity = create_activity(
            created_by=self.christophe,
            owner_profile=self.christophe,
            title="Activity Alumni",
        )
        request_activity_group_eligibility(
            actor=self.christophe,
            activity=activity,
            group=group,
        )
        self.assertFalse(profile_is_eligible_for_activity(self.member, activity))
        join_group(profile=self.member, group=group)
        self.assertTrue(profile_is_eligible_for_activity(self.member, activity))
        membership = GroupMembership.objects.get(group=group, profile=self.member)
        membership.status = GroupMembershipStatus.LEFT
        membership.save(update_fields=["status", "updated_at"])
        self.assertFalse(profile_is_eligible_for_activity(self.member, activity))

    def test_new_journey_enforces_group_eligibility_server_side(self):
        group = self.group(policy=GroupMembershipPolicy.OPEN)
        activity = create_activity(
            created_by=self.christophe,
            owner_profile=self.christophe,
            title="Activity réservée",
        )
        request_activity_group_eligibility(
            actor=self.christophe,
            activity=activity,
            group=group,
        )
        with self.assertRaises(ValidationError):
            create_journey(
                initiated_by=self.outsider,
                beneficiary=self.outsider,
                activity=activity,
                workflow=WorkflowKind.REGISTRATION,
            )
        join_group(profile=self.member, group=group)
        journey = create_journey(
            initiated_by=self.member,
            beneficiary=self.member,
            activity=activity,
            workflow=WorkflowKind.REGISTRATION,
        )
        self.assertEqual(journey.beneficiary, self.member)

    def test_membership_change_does_not_invalidate_existing_journey(self):
        group = self.group(policy=GroupMembershipPolicy.OPEN)
        activity = create_activity(
            created_by=self.christophe,
            owner_profile=self.christophe,
            title="Activity historique",
        )
        request_activity_group_eligibility(
            actor=self.christophe,
            activity=activity,
            group=group,
        )
        join_group(profile=self.member, group=group)
        journey = create_journey(
            initiated_by=self.member,
            beneficiary=self.member,
            activity=activity,
            workflow=WorkflowKind.REGISTRATION,
        )
        membership = GroupMembership.objects.get(group=group, profile=self.member)
        membership.status = GroupMembershipStatus.LEFT
        membership.save(update_fields=["status", "updated_at"])
        journey.expires_at = None
        journey.save(update_fields=["expires_at", "updated_at"])
        self.assertTrue(journey.pk)

    def test_archived_group_refuses_new_join_request_and_usage(self):
        group = self.group(policy=GroupMembershipPolicy.REQUEST)
        group.status = "archived"
        group.save(update_fields=["status", "updated_at"])
        with self.assertRaises(ValidationError):
            request_to_join(profile=self.member, group=group)
        activity = create_activity(
            created_by=self.christophe,
            owner_profile=self.christophe,
            title="Activity archive test",
        )
        with self.assertRaises(ValidationError):
            request_activity_group_eligibility(
                actor=self.christophe,
                activity=activity,
                group=group,
            )
