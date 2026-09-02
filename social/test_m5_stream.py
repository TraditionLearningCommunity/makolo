from django.contrib.auth import get_user_model
from django.test import TestCase

from activities.models import Activity, ActivityStatus, ActivityVisibility
from groups.models import Group, GroupMembership, GroupMembershipStatus
from organizations.models import Organization, OrganizationFollow

from .action_stream import build_action_stream
from .services import share_activity_to_group


User = get_user_model()


class M5ActionStreamTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="stream-user", email="stream-user@example.test", password="StrongPass2026!")
        self.owner = User.objects.create_user(username="stream-owner", email="stream-owner@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="Stream Space", created_by=self.owner)
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.owner, title="Stream Activity", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC
        )
        self.private_activity = Activity.objects.create(
            space=self.space, created_by=self.owner, title="Hidden Stream Activity", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PRIVATE
        )

    def test_follow_produces_bounded_stream_and_filters_private_activity(self):
        OrganizationFollow.objects.create(organization=self.space, user=self.user)
        page = build_action_stream(self.user, limit=1)
        self.assertLessEqual(len(page.items), 1)
        self.assertIn(self.activity.pk, [item.activity.pk for item in page.items if item.activity])
        self.assertNotIn(self.private_activity.pk, [item.activity.pk for item in page.items if item.activity])

    def test_group_share_deduplicates_activity_and_grants_no_right(self):
        group = Group.objects.create(name="Stream Group", owner_profile=self.owner, created_by=self.owner)
        GroupMembership.objects.create(group=group, profile=self.user, status=GroupMembershipStatus.ACTIVE)
        OrganizationFollow.objects.create(organization=self.space, user=self.user)
        share_activity_to_group(actor=self.user, group=group, activity=self.activity, body="À faire")
        page = build_action_stream(self.user, limit=20)
        activity_items = [item for item in page.items if item.activity and item.activity.pk == self.activity.pk]
        self.assertEqual(len(activity_items), 1)
        self.assertIn("Votre Groupe", activity_items[0].reasons)
        self.assertFalse(self.user.access_rights.filter(activity=self.activity).exists())
