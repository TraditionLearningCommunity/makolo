from django.contrib.auth import get_user_model
from django.test import TestCase

from activities.models import Activity, ActivityStatus, ActivityVisibility
from discovery.models import ActivityBookmark
from groups.models import Group, GroupMembership, GroupMembershipStatus
from organizations.models import Organization, OrganizationFollow
from services.models import ServiceDetails, ServiceKind
from social.services import share_activity_to_group

from .recommendations import build_activity_recommendations


User = get_user_model()


class M5RecommendationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rec-user", email="rec-user@example.test", password="StrongPass2026!")
        self.owner = User.objects.create_user(username="rec-owner", email="rec-owner@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="Recommendation Space", created_by=self.owner)
        self.other_space = Organization.objects.create(name="Other Recommendation Space", created_by=self.owner)
        self.service_activity = Activity.objects.create(space=self.space, created_by=self.owner, title="Service Activity", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC)
        ServiceDetails.objects.create(activity=self.service_activity, service_kind=ServiceKind.ORIENTATION)
        self.generic_activity = Activity.objects.create(space=self.other_space, created_by=self.owner, title="Generic Activity", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC)
        self.private_activity = Activity.objects.create(space=self.space, created_by=self.owner, title="Private Activity", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PRIVATE)

    def test_follow_reason_is_explicit_and_private_activity_is_filtered(self):
        OrganizationFollow.objects.create(organization=self.space, user=self.user)
        results = build_activity_recommendations(self.user)
        ids = [row.activity.pk for row in results]
        self.assertIn(self.service_activity.pk, ids)
        service = next(row for row in results if row.activity.pk == self.service_activity.pk)
        self.assertIn("following_space", [reason.code for reason in service.reasons])
        self.assertNotIn(self.private_activity.pk, ids)
        self.assertFalse(any(hasattr(row, "followers_count") for row in results))

    def test_group_share_reason_and_no_duplicate_result(self):
        group = Group.objects.create(name="Recommendation Group", owner_profile=self.owner, created_by=self.owner)
        GroupMembership.objects.create(group=group, profile=self.user, status=GroupMembershipStatus.ACTIVE)
        share_activity_to_group(actor=self.user, group=group, activity=self.generic_activity, body="Utile")
        OrganizationFollow.objects.create(organization=self.other_space, user=self.user)
        matching = [row for row in build_activity_recommendations(self.user) if row.activity.pk == self.generic_activity.pk]
        self.assertEqual(len(matching), 1)
        codes = [reason.code for reason in matching[0].reasons]
        self.assertIn("group_relevance", codes)
        self.assertIn("following_space", codes)

    def test_bookmark_similarity_supports_non_event_activity(self):
        ActivityBookmark.objects.create(user=self.user, activity=self.service_activity)
        similar = Activity.objects.create(space=self.other_space, created_by=self.owner, title="Another Service", status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC)
        ServiceDetails.objects.create(activity=similar, service_kind=ServiceKind.CAREER_SUPPORT)
        match = next(row for row in build_activity_recommendations(self.user) if row.activity.pk == similar.pk)
        self.assertEqual(match.vertical, "service")
        self.assertIn("bookmarked_similar_activity", [reason.code for reason in match.reasons])
