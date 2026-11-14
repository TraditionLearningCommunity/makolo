import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind


class NativeInvitationTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.beneficiary = users.objects.create_user(
            username="invitation-native-beneficiary",
            email="invitation-native-beneficiary@example.test",
            password="test-pass-2026",
        )
        self.other = users.objects.create_user(
            username="invitation-native-other",
            email="invitation-native-other@example.test",
            password="test-pass-2026",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.other, created_by=self.other,
            title="Invitation à un atelier",
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=3),
            end_at=timezone.now() + timedelta(days=3, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.beneficiary,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.INVITATION,
            status=JourneyStatus.SUBMITTED,
        )
        self.url = reverse(
            "personal-detail-projections:journey-invitation",
            kwargs={"pk": self.journey.pk},
        )

    def decide(self, decision):
        return self.client.post(
            self.url,
            data=json.dumps({"decision": decision}),
            content_type="application/json",
        )

    def test_unauthenticated_and_foreign_profiles_cannot_decide(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.decide("accept").status_code, 404)
        self.assertEqual(self.journey.status, JourneyStatus.SUBMITTED)
        self.assertEqual(Access.objects.count(), 0)

    def test_accept_is_idempotent_and_issues_access_once(self):
        self.client.force_login(self.beneficiary)
        self.assertEqual(
            set(self.client.get(self.url).json()["capabilities"]),
            {"accept", "decline"},
        )
        first = self.decide("accept")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["status"], "confirmed")
        self.assertIsNotNone(first.json()["access_id"])
        second = self.decide("accept")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["access_id"], first.json()["access_id"])
        self.assertEqual(Access.objects.filter(journey=self.journey).count(), 1)
        self.assertEqual(self.client.get(self.url).json()["capabilities"], [])
        self.assertEqual(self.decide("decline").status_code, 400)

    def test_decline_is_idempotent_and_never_issues_access(self):
        self.client.force_login(self.beneficiary)
        self.assertEqual(self.decide("decline").json()["status"], "cancelled")
        self.assertEqual(self.decide("decline").json()["status"], "cancelled")
        self.assertEqual(self.decide("accept").status_code, 400)
        self.assertEqual(Access.objects.filter(journey=self.journey).count(), 0)

    def test_rejects_non_invitation_journey(self):
        self.journey.workflow = WorkflowKind.REGISTRATION
        self.journey.save()
        self.client.force_login(self.beneficiary)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.decide("accept").status_code, 404)

    def test_rejects_unknown_or_incomplete_decision(self):
        self.client.force_login(self.beneficiary)
        self.assertEqual(self.decide("apply").status_code, 400)
        result = self.client.post(
            self.url, data=json.dumps({"decision": "accept", "is_admin": True}),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 400)
        self.assertEqual(Access.objects.count(), 0)
