from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessStatus
from activities.models import Activity, Occurrence, OccurrenceStatus, OccurrenceTimingKind
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .models import PlacementPlan


User = get_user_model()


class M8CParticipantOccurrenceLiveProjectionTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(username="m8c-live-owner", email="m8c-live-owner@example.test", password="pw")
        self.participant = User.objects.create_user(username="m8c-live", email="m8c-live@example.test", password="pw")
        self.activity = Activity.objects.create(
            created_by=self.owner,
            owner_profile=self.owner,
            title="M8-C action réelle",
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Session M8-C",
            start_at=self.now - timedelta(minutes=5),
            end_at=self.now + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.access = Access.objects.create(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            status=AccessStatus.VALID,
        )

    def _payload(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("operations_api:occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_before_phase_does_not_push_onsite_action(self):
        self.occurrence.start_at = self.now + timedelta(hours=4)
        self.occurrence.end_at = self.now + timedelta(hours=6)
        self.occurrence.save(update_fields=["start_at", "end_at", "updated_at"])
        payload = self._payload()
        self.assertEqual(payload["phase"], "before")
        self.assertEqual(payload["next_action"]["type"], "none")
        self.assertEqual(payload["next_action"]["reason"], "before_no_immediate_action")

    def test_pending_access_is_waiting_not_regularization(self):
        self.access.status = AccessStatus.PENDING
        self.access.save(update_fields=["status", "updated_at"])
        payload = self._payload()
        self.assertEqual(payload["next_action"]["type"], "access_wait")
        self.assertEqual(payload["next_action"]["reason"], "participant_access_pending")
        access_check = next(
            row for row in payload["operational_readiness"]["contributors"] if row["key"] == "operations.access.me"
        )
        self.assertEqual(access_check["state"], "waiting")

    def test_missing_required_placement_is_waiting_not_participant_action(self):
        PlacementPlan.objects.create(
            occurrence=self.occurrence,
            key="seat",
            label="Placement",
            required=True,
        )
        payload = self._payload()
        placement = next(
            row for row in payload["operational_readiness"]["contributors"] if row["key"] == "operations.placement.me"
        )
        self.assertEqual(placement["state"], "waiting")
        self.assertEqual(placement["reason"], "participant_placement_missing")

    def test_date_only_remains_date_only_without_fake_time(self):
        target_date = (self.now + timedelta(days=2)).date()
        self.occurrence.timing_kind = OccurrenceTimingKind.DATE_ONLY
        self.occurrence.start_at = None
        self.occurrence.end_at = None
        self.occurrence.start_date = target_date
        self.occurrence.end_date = target_date
        self.occurrence.save(
            update_fields=["timing_kind", "start_at", "end_at", "start_date", "end_date", "updated_at"]
        )
        payload = self._payload()
        self.assertEqual(payload["phase"], "before")
        self.assertEqual(payload["timing"]["timing_kind"], "date_only")
        self.assertIsNone(payload["timing"]["start_at"])
        self.assertEqual(payload["timing"]["start_date"], target_date.isoformat())
