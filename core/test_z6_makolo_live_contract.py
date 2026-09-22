from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import AccessStatus
from access.services import issue_access
from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind


class Z6MakoloLiveContractTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(
            username="z6-live-owner",
            email="z6-live-owner@makolo.test",
            password="pw",
        )
        self.participant = User.objects.create_user(
            username="z6-live-participant",
            email="z6-live-participant@makolo.test",
            password="pw",
        )
        self.outsider = User.objects.create_user(
            username="z6-live-outsider",
            email="z6-live-outsider@makolo.test",
            password="pw",
        )
        self.activity = Activity.objects.create(
            title="Makolo Live Z6",
            created_by=self.owner,
            owner_profile=self.owner,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now - timedelta(minutes=5),
            end_at=self.now + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.access = issue_access(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=journey,
            status=AccessStatus.VALID,
            source_key="z6:live",
        )

    def _live(self):
        return self.client.get(
            reverse("operations_api:occurrence-live", args=[self.occurrence.pk])
        )

    def test_live_reuses_operations_and_stays_participant_safe(self):
        self.client.force_login(self.participant)
        response = self._live()
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["perspective"], "participant")
        self.assertEqual(data["phase"], "live")
        self.assertIn("timing", data)
        self.assertIn("spatial", data)
        self.assertIn("operational_readiness", data)
        self.assertIn("next_action", data)
        rendered = str(data).lower()
        self.assertNotIn("credential", rendered)
        self.assertNotIn("permission", rendered)
        self.assertNotIn("assignment_count", rendered)
        self.assertNotIn("scanner", rendered)

    def test_physical_access_does_not_invent_media_access_or_presence(self):
        self.client.force_login(self.participant)
        data = self._live().json()

        self.assertTrue(data["access"])
        self.assertNotIn("media", data)
        self.assertNotIn("stream", data)
        self.assertNotIn("presence", data)
        self.assertNotIn("current_position", data["spatial"])

    def test_live_phase_is_derived_from_occurrence_time_not_access_existence(self):
        self.occurrence.start_at = self.now + timedelta(hours=4)
        self.occurrence.end_at = self.now + timedelta(hours=6)
        self.occurrence.save(update_fields=["start_at", "end_at", "updated_at"])

        self.client.force_login(self.participant)
        before = self._live().json()
        self.assertEqual(before["phase"], "before")

        self.occurrence.status = OccurrenceStatus.COMPLETED
        self.occurrence.start_at = self.now - timedelta(hours=3)
        self.occurrence.end_at = self.now - timedelta(minutes=5)
        self.occurrence.save(
            update_fields=["status", "start_at", "end_at", "updated_at"]
        )
        after = self._live().json()
        self.assertEqual(after["phase"], "after")
        self.assertEqual(after["next_action"]["type"], "none")

    def test_outsider_cannot_open_participant_live_by_uuid(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self._live().status_code, 404)
