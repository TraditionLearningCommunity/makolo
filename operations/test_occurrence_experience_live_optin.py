"""Journey/Occurrence integration: Jour J works without a published Live."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.models import Journey, WorkflowKind, JourneyStatus


User = get_user_model()


class LiveOptInOccurrenceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="l34-owner", email="l34-owner@example.test",
        )
        self.participant = User.objects.create_user(
            username="l34-participant", email="l34-participant@example.test",
        )
        self.outsider = User.objects.create_user(
            username="l34-outsider", email="l34-outsider@example.test",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.owner, created_by=self.owner,
            title="Occurrence sans Live par défaut",
        )
        grant_activity_role(
            profile=self.owner, activity=self.activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() - timedelta(minutes=5),
            end_at=timezone.now() + timedelta(hours=2),
        )
        Journey.objects.create(
            initiated_by=self.participant, beneficiary=self.participant,
            activity=self.activity, occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION, status=JourneyStatus.CONFIRMED,
        )
        self.client = APIClient()
        self.day_url = (
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/experience/day-of/"
        )
        self.live_url = (
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/experience/live/"
        )
        self.toggle_url = (
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/experience/live-configuration/"
        )

    def test_day_of_remains_accessible_without_live(self):
        self.client.force_authenticate(user=self.participant)
        result = self.client.get(self.day_url)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.data["data"]["live"]["available"])
        self.assertNotIn("live", result.data["data"]["links"])
        self.assertEqual(self.client.get(self.live_url).status_code, 404)

    def test_owner_explicitly_enables_and_disables_live(self):
        self.client.force_authenticate(user=self.owner)
        enabled = self.client.post(self.toggle_url, {"enabled": True}, format="json")
        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(enabled.data["live_enabled"])

        self.client.force_authenticate(user=self.participant)
        available = self.client.get(self.day_url)
        self.assertEqual(available.status_code, 200)
        self.assertTrue(available.data["data"]["live"]["available"])
        live = self.client.get(self.live_url)
        self.assertEqual(live.status_code, 200)
        self.assertIn("coverage", live.data["data"]["knowledge"])

        self.client.force_authenticate(user=self.owner)
        disabled = self.client.post(self.toggle_url, {"enabled": False}, format="json")
        self.assertEqual(disabled.status_code, 200)
        self.client.force_authenticate(user=self.participant)
        self.assertEqual(self.client.get(self.live_url).status_code, 404)

    def test_outsider_cannot_read_or_publish(self):
        self.client.force_authenticate(user=self.outsider)
        self.assertEqual(self.client.get(self.day_url).status_code, 404)
        self.assertEqual(
            self.client.post(self.toggle_url, {"enabled": True}, format="json").status_code,
            403,
        )
        self.occurrence.refresh_from_db()
        self.assertFalse(self.occurrence.live_enabled)

    def test_configuration_rejects_non_boolean(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            self.toggle_url, {"enabled": "true"}, format="json",
        )
        self.assertEqual(response.status_code, 400)
