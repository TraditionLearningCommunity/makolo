from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from activities.services import create_activity
from crm.canonical_models import Audience, AudienceMember
from groups.community_group_services import create_community_group
from groups.community_services import (
    decide_activity_group_eligibility,
    join_group,
    profile_is_eligible_for_activity,
    reject_join_request,
    request_activity_group_eligibility,
    request_to_join,
    revoke_activity_group_eligibility,
)
from groups.models import (
    ActivityGroupEligibilityStatus,
    GroupDiscoverability,
    GroupMembership,
    GroupMembershipPolicy,
    GroupStatus,
)
from notifications.models import Notification


User = get_user_model()
PASSWORD = "Task27-Boundaries-2026!"


class Task27BoundaryTests(TestCase):
    def setUp(self):
        self.group_owner = User.objects.create_user(
            username="t27-boundary-owner",
            email="t27-boundary-owner@example.test",
            password=PASSWORD,
        )
        self.activity_owner = User.objects.create_user(
            username="t27-boundary-activity",
            email="t27-boundary-activity@example.test",
            password=PASSWORD,
        )
        self.member = User.objects.create_user(
            username="t27-boundary-member",
            email="t27-boundary-member@example.test",
            password=PASSWORD,
        )
        self.outsider = User.objects.create_user(
            username="t27-boundary-outsider",
            email="t27-boundary-outsider@example.test",
            password=PASSWORD,
        )
        self.group = create_community_group(
            actor=self.group_owner,
            name="Anciens MAPENDO Boundary",
            discoverability=GroupDiscoverability.LISTED,
            membership_policy=GroupMembershipPolicy.OPEN,
        )
        self.activity = create_activity(
            created_by=self.activity_owner,
            owner_profile=self.activity_owner,
            title="Voyage Alumni Boundary",
        )

    def test_cross_owner_usage_never_populates_crm_or_copies_memberships(self):
        join_group(profile=self.member, group=self.group)
        membership_count = GroupMembership.objects.count()
        audience_count = Audience.objects.count()
        audience_member_count = AudienceMember.objects.count()

        relation, _ = request_activity_group_eligibility(
            actor=self.activity_owner,
            activity=self.activity,
            group=self.group,
        )
        decide_activity_group_eligibility(
            actor=self.group_owner,
            eligibility=relation,
            approve=True,
        )

        self.assertEqual(GroupMembership.objects.count(), membership_count)
        self.assertEqual(Audience.objects.count(), audience_count)
        self.assertEqual(AudienceMember.objects.count(), audience_member_count)
        self.assertEqual(self.group.activity_eligibilities.count(), 1)

    def test_cross_owner_request_and_decision_use_canonical_notifications(self):
        with self.captureOnCommitCallbacks(execute=True):
            relation, _ = request_activity_group_eligibility(
                actor=self.activity_owner,
                activity=self.activity,
                group=self.group,
            )
        request_notification = Notification.objects.filter(recipient=self.group_owner).latest("created_at")
        self.assertEqual(request_notification.activity_id, self.activity.pk)
        self.assertEqual(request_notification.metadata["group_id"], str(self.group.pk))
        self.assertNotIn("email", request_notification.metadata)
        self.assertNotIn("phone", request_notification.metadata)

        with self.captureOnCommitCallbacks(execute=True):
            decide_activity_group_eligibility(
                actor=self.group_owner,
                eligibility=relation,
                approve=False,
            )
        decision = Notification.objects.filter(recipient=self.activity_owner).latest("created_at")
        self.assertEqual(decision.metadata["status"], ActivityGroupEligibilityStatus.REJECTED)

    def test_reject_then_request_again_then_revoke(self):
        relation, _ = request_activity_group_eligibility(
            actor=self.activity_owner,
            activity=self.activity,
            group=self.group,
        )
        decide_activity_group_eligibility(
            actor=self.group_owner,
            eligibility=relation,
            approve=False,
        )
        relation.refresh_from_db()
        self.assertEqual(relation.status, ActivityGroupEligibilityStatus.REJECTED)

        relation, created = request_activity_group_eligibility(
            actor=self.activity_owner,
            activity=self.activity,
            group=self.group,
        )
        self.assertFalse(created)
        self.assertEqual(relation.status, ActivityGroupEligibilityStatus.REQUESTED)
        decide_activity_group_eligibility(
            actor=self.group_owner,
            eligibility=relation,
            approve=True,
        )
        relation.refresh_from_db()
        self.assertEqual(relation.status, ActivityGroupEligibilityStatus.APPROVED)
        revoke_activity_group_eligibility(actor=self.activity_owner, eligibility=relation)
        relation.refresh_from_db()
        self.assertEqual(relation.status, ActivityGroupEligibilityStatus.REVOKED)
        self.assertTrue(profile_is_eligible_for_activity(self.outsider, self.activity))

    def test_rejected_join_request_never_creates_membership(self):
        self.group.membership_policy = GroupMembershipPolicy.REQUEST
        self.group.save(update_fields=["membership_policy", "updated_at"])
        request, _ = request_to_join(profile=self.member, group=self.group)
        reject_join_request(actor=self.group_owner, request=request)
        request.refresh_from_db()
        self.assertEqual(request.status, "rejected")
        self.assertFalse(GroupMembership.objects.filter(group=self.group, profile=self.member).exists())

    def test_archiving_group_does_not_turn_existing_restriction_public(self):
        relation = request_activity_group_eligibility(
            actor=self.group_owner,
            activity=create_activity(
                created_by=self.group_owner,
                owner_profile=self.group_owner,
                title="Activity Restricted Then Archived",
            ),
            group=self.group,
        )[0]
        self.assertEqual(relation.status, ActivityGroupEligibilityStatus.APPROVED)
        restricted_activity = relation.activity
        self.assertFalse(profile_is_eligible_for_activity(self.outsider, restricted_activity))
        self.group.status = GroupStatus.ARCHIVED
        self.group.save(update_fields=["status", "updated_at"])
        self.assertFalse(profile_is_eligible_for_activity(self.outsider, restricted_activity))

    def test_archived_group_usage_request_cannot_be_approved(self):
        relation, _ = request_activity_group_eligibility(
            actor=self.activity_owner,
            activity=self.activity,
            group=self.group,
        )
        self.group.status = GroupStatus.ARCHIVED
        self.group.save(update_fields=["status", "updated_at"])
        with self.assertRaises(ValidationError):
            decide_activity_group_eligibility(
                actor=self.group_owner,
                eligibility=relation,
                approve=True,
            )
