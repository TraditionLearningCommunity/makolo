from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from activities.services import create_activity
from groups.community_group_services import create_community_group
from groups.community_services import (
    approve_join_request,
    join_group,
    request_activity_group_eligibility,
    request_to_join,
)
from groups.models import (
    ActivityGroupEligibility,
    GroupDiscoverability,
    GroupJoinRequest,
    GroupMembership,
    GroupMembershipPolicy,
)


User = get_user_model()
PASSWORD = "Task27-Concurrency-2026!"


@skipUnless(connection.vendor == "postgresql", "Ce test exerce les verrous Groups PostgreSQL réels.")
class Task27GroupConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.owner = User.objects.create_user(
            username="t27-race-owner",
            email="t27-race-owner@example.test",
            password=PASSWORD,
        )
        self.member = User.objects.create_user(
            username="t27-race-member",
            email="t27-race-member@example.test",
            password=PASSWORD,
        )
        self.activity_owner = User.objects.create_user(
            username="t27-race-activity",
            email="t27-race-activity@example.test",
            password=PASSWORD,
        )
        self.open_group = create_community_group(
            actor=self.owner,
            name="T27 Open Race",
            discoverability=GroupDiscoverability.LISTED,
            membership_policy=GroupMembershipPolicy.OPEN,
        )
        self.request_group = create_community_group(
            actor=self.owner,
            name="T27 Request Race",
            discoverability=GroupDiscoverability.LISTED,
            membership_policy=GroupMembershipPolicy.REQUEST,
        )
        self.activity = create_activity(
            created_by=self.activity_owner,
            owner_profile=self.activity_owner,
            title="T27 Eligibility Race",
        )

    def _join_open(self, barrier):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            profile = User.objects.get(pk=self.member.pk)
            group = self.open_group.__class__.objects.get(pk=self.open_group.pk)
            membership, _ = join_group(profile=profile, group=group)
            return str(membership.pk)
        finally:
            connection.close()

    def test_double_open_join_creates_one_membership(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [
                future.result(timeout=15)
                for future in [executor.submit(self._join_open, barrier) for _ in range(2)]
            ]
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(
            GroupMembership.objects.filter(group=self.open_group, profile=self.member).count(),
            1,
        )

    def _request_usage(self, barrier):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            actor = User.objects.get(pk=self.activity_owner.pk)
            activity = self.activity.__class__.objects.get(pk=self.activity.pk)
            group = self.open_group.__class__.objects.get(pk=self.open_group.pk)
            relation, _ = request_activity_group_eligibility(
                actor=actor,
                activity=activity,
                group=group,
            )
            return str(relation.pk)
        finally:
            connection.close()

    def test_double_eligibility_request_creates_one_relation(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [
                future.result(timeout=15)
                for future in [executor.submit(self._request_usage, barrier) for _ in range(2)]
            ]
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(
            ActivityGroupEligibility.objects.filter(
                group=self.open_group,
                activity=self.activity,
            ).count(),
            1,
        )

    def _approve_request(self, barrier, request_id):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            actor = User.objects.get(pk=self.owner.pk)
            join_request = GroupJoinRequest.objects.get(pk=request_id)
            _, membership = approve_join_request(actor=actor, request=join_request)
            return str(membership.pk)
        finally:
            connection.close()

    def test_double_join_request_approval_creates_one_membership(self):
        join_request, _ = request_to_join(profile=self.member, group=self.request_group)
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [
                future.result(timeout=15)
                for future in [
                    executor.submit(self._approve_request, barrier, join_request.pk)
                    for _ in range(2)
                ]
            ]
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(
            GroupMembership.objects.filter(group=self.request_group, profile=self.member).count(),
            1,
        )
        self.assertEqual(
            GroupJoinRequest.objects.filter(pk=join_request.pk, status="approved").count(),
            1,
        )
