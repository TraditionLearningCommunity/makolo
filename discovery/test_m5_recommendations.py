from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from discovery.models import ActivityBookmark
from discovery.recommendations import build_activity_recommendations
from events.models import Event
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, OrganizationFollow
from services.models import ServiceDetails, ServiceKind


User = get_user_model()


class M5RecommendationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="m5-rec-user", email="m5-rec-user@example.test", password="StrongPass2026!")
        self.owner = User.objects.create_user(username="m5-rec-owner", email="m5-rec-owner@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="M5 Recommendation Space", created_by=self.owner, public_profile=True)

        self.event_activity = Activity.objects.create(
            space=self.space, created_by=self.owner, title="M5 Event Activity",
            status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC,
        )
        Event.objects.create(activity=self.event_activity, slug="m5-event-activity")
        Occurrence.objects.create(
            activity=self.event_activity,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )

        self.event_candidate = Activity.objects.create(
            space=self.space, created_by=self.owner, title="M5 Event Candidate",
            status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC,
        )
        Event.objects.create(activity=self.event_candidate, slug="m5-event-candidate")
        Occurrence.objects.create(
            activity=self.event_candidate,
            start_at=timezone.now() + timedelta(days=3),
            end_at=timezone.now() + timedelta(days=3, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )

        self.service_activity = Activity.objects.create(
            space=self.space, created_by=self.owner, title="M5 Service Candidate",
            status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC,
        )
        ServiceDetails.objects.create(activity=self.service_activity, service_kind=ServiceKind.ORIENTATION)

    def test_follow_reason_and_multi_vertical_activity_results(self):
        OrganizationFollow.objects.create(organization=self.space, user=self.user)
        rows = build_activity_recommendations(self.user)
        by_id = {row.activity_id if hasattr(row, "activity_id") else row.activity.pk: row for row in rows}
        self.assertIn(self.event_candidate.pk, by_id)
        self.assertIn(self.service_activity.pk, by_id)
        self.assertEqual(by_id[self.event_candidate.pk].vertical, "event")
        self.assertEqual(by_id[self.service_activity.pk].vertical, "service")
        self.assertIn("following_space", {reason.code for reason in by_id[self.service_activity.pk].reasons})

    def test_bookmark_and_private_history_supply_explainable_coarse_reasons(self):
        ActivityBookmark.objects.create(user=self.user, activity=self.event_activity)
        Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.event_activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
            fulfilled_at=timezone.now(),
        )
        rows = build_activity_recommendations(self.user)
        candidate = next(row for row in rows if row.activity.pk == self.event_candidate.pk)
        codes = {reason.code for reason in candidate.reasons}
        self.assertIn("bookmarked_similar_activity", codes)
        self.assertIn("past_activity_interest", codes)
        self.assertNotIn(str(self.event_activity.pk), " ".join(reason.label for reason in candidate.reasons))

    def test_private_activity_is_removed_before_ranking(self):
        private_activity = Activity.objects.create(
            space=self.space, created_by=self.owner, title="M5 Private Candidate",
            status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PRIVATE,
        )
        OrganizationFollow.objects.create(organization=self.space, user=self.user)
        ids = {row.activity.pk for row in build_activity_recommendations(self.user)}
        self.assertNotIn(private_activity.pk, ids)
