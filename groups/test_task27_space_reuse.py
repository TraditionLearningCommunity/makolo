from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from activities.services import create_activity
from groups.community_group_services import create_community_group
from groups.community_services import (
    decide_activity_group_eligibility,
    join_group,
    request_activity_group_eligibility,
)
from groups.models import (
    ActivityGroupEligibilityStatus,
    Group,
    GroupDiscoverability,
    GroupMembership,
    GroupMembershipPolicy,
)
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.services import create_organization


User = get_user_model()
PASSWORD = "Task27-Space-Reuse-2026!"


class Task27SpaceReuseTests(TestCase):
    def setUp(self):
        self.group_owner = User.objects.create_user(
            username="t27-space-group-owner",
            email="t27-space-group-owner@example.test",
            password=PASSWORD,
        )
        self.space_owner = User.objects.create_user(
            username="t27-space-owner",
            email="t27-space-owner@example.test",
            password=PASSWORD,
        )
        self.outsider = User.objects.create_user(
            username="t27-space-outsider",
            email="t27-space-outsider@example.test",
            password=PASSWORD,
        )
        self.member = User.objects.create_user(
            username="t27-space-member",
            email="t27-space-member@example.test",
            password=PASSWORD,
        )
        self.space = create_organization(
            creator=self.space_owner,
            name="Mulykap T27 Cross Space",
        )

    def test_space_only_group_is_visible_to_space_authority_but_hidden_from_outsider(self):
        group = create_community_group(
            actor=self.space_owner,
            space=self.space,
            name="Employés Mulykap T27",
            discoverability=GroupDiscoverability.SPACE_ONLY,
            membership_policy=GroupMembershipPolicy.INVITE_ONLY,
        )
        self.client.force_login(self.space_owner)
        self.assertEqual(
            self.client.get(reverse("groups:detail", kwargs={"slug": group.slug})).status_code,
            200,
        )
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(reverse("groups:detail", kwargs={"slug": group.slug})).status_code,
            404,
        )

    def test_forged_space_creation_is_denied(self):
        with self.assertRaises(PermissionDenied):
            create_community_group(
                actor=self.outsider,
                space=self.space,
                name="Groupe forgé",
                discoverability=GroupDiscoverability.SPACE_ONLY,
            )

    def test_personal_group_cannot_use_space_only_discoverability(self):
        with self.assertRaises(ValidationError):
            create_community_group(
                actor=self.group_owner,
                name="Personnel SPACE_ONLY invalide",
                discoverability=GroupDiscoverability.SPACE_ONLY,
            )

    def test_same_personal_group_is_reused_by_space_activity_without_copy(self):
        group = create_community_group(
            actor=self.group_owner,
            name="Anciens MAPENDO Cross Space",
            discoverability=GroupDiscoverability.LISTED,
            membership_policy=GroupMembershipPolicy.OPEN,
        )
        join_group(profile=self.member, group=group)
        original_group_count = Group.objects.count()
        original_membership_count = GroupMembership.objects.count()

        activity = create_activity(
            created_by=self.space_owner,
            space=self.space,
            title="Voyage Alumni Mulykap T27",
        )
        relation, _ = request_activity_group_eligibility(
            actor=self.space_owner,
            activity=activity,
            group=group,
        )
        self.assertEqual(relation.status, ActivityGroupEligibilityStatus.REQUESTED)
        decide_activity_group_eligibility(
            actor=self.group_owner,
            eligibility=relation,
            approve=True,
        )
        relation.refresh_from_db()
        self.assertEqual(relation.status, ActivityGroupEligibilityStatus.APPROVED)
        self.assertEqual(Group.objects.count(), original_group_count)
        self.assertEqual(GroupMembership.objects.count(), original_membership_count)
        group.refresh_from_db()
        self.assertEqual(group.owner_profile, self.group_owner)
        self.assertIsNone(group.space)

        member_journey = create_journey(
            initiated_by=self.member,
            beneficiary=self.member,
            activity=activity,
            workflow=WorkflowKind.REGISTRATION,
        )
        self.assertEqual(member_journey.beneficiary, self.member)
        with self.assertRaises(ValidationError):
            create_journey(
                initiated_by=self.outsider,
                beneficiary=self.outsider,
                activity=activity,
                workflow=WorkflowKind.REGISTRATION,
            )
