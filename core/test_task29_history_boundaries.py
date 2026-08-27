from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from access.models import Access, AccessStatus
from activities.models import Activity, ActivityStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind


User = get_user_model()


class Task29HistoryBoundaryTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="t29-history-profile",
            email="t29-history-profile@example.test",
            password="Task29-2026!",
        )
        self.other = User.objects.create_user(
            username="t29-history-other",
            email="t29-history-other@example.test",
            password="Task29-2026!",
        )
        self.activity = Activity.objects.create(
            title="Mémoire Kolwezi T29",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        self.client.force_login(self.profile)

    def test_history_search_and_filters_remain_in_personal_scope(self):
        own = Journey.objects.create(
            initiated_by=self.profile,
            beneficiary=self.profile,
            activity=self.activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.REJECTED,
        )
        foreign_activity = Activity.objects.create(
            title="Mémoire Kolwezi étrangère T29",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.other,
            activity=foreign_activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.REJECTED,
        )

        response = self.client.get(
            reverse("core:participant-history"),
            {"q": "Kolwezi", "type": "journeys"},
        )
        self.assertEqual(response.status_code, 200)
        ids = [item["journey_card"]["journey"].pk for item in response.context["history_items"]]
        self.assertEqual(ids, [own.pk])
        self.assertContains(response, "Mémoire Kolwezi T29")
        self.assertNotContains(response, "Mémoire Kolwezi étrangère T29")

    def test_personal_access_history_does_not_link_foreign_journey(self):
        foreign_journey = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.other,
            activity=self.activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=self.activity,
            journey=foreign_journey,
            status=AccessStatus.USED,
        )

        response = self.client.get(reverse("core:participant-history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
        )
        self.assertNotContains(
            response,
            reverse("core:participant-journey-detail", kwargs={"pk": foreign_journey.pk}),
        )
        detail = self.client.get(
            reverse("core:participant-journey-detail", kwargs={"pk": foreign_journey.pk})
        )
        self.assertEqual(detail.status_code, 404)

    def test_created_by_does_not_make_space_activity_personally_owned(self):
        personal = Activity.objects.create(
            title="Activity personnelle T29",
            created_by=self.profile,
            owner_profile=self.profile,
            status=ActivityStatus.PUBLISHED,
        )
        Activity.objects.create(
            title="Activity seulement créée T29",
            created_by=self.profile,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )

        response = self.client.get(reverse("core:participant-home"))
        organized_ids = {activity.pk for activity in response.context["organized_activities"]}
        self.assertIn(personal.pk, organized_ids)
        self.assertEqual(len(organized_ids), 1)
