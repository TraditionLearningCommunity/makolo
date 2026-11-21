from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.models import Journey, JourneyStatus, WorkflowKind


User = get_user_model()


class CanonicalOccurrenceWebTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="web-occ-owner", email="owner-web-occ@test.local")
        self.beneficiary = User.objects.create_user(username="web-occ-beneficiary", email="benef-web-occ@test.local")
        self.activity = Activity.objects.create(
            title="Formation Web", owner_profile=self.owner, created_by=self.owner,
        )
        grant_activity_role(
            profile=self.owner, activity=self.activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
        )
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity, label="Atelier",
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=2),
        )
        Journey.objects.create(
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.day_url = reverse(
            "core:participant-occurrence-day-of", kwargs={"pk": self.occurrence.pk},
        )
        self.live_url = reverse(
            "core:participant-occurrence-live", kwargs={"pk": self.occurrence.pk},
        )

    def test_personal_day_of_exists_without_live(self):
        self.client.force_login(self.beneficiary)
        day = self.client.get(self.day_url)
        self.assertEqual(day.status_code, 200)
        self.assertContains(day, "Jour J")
        self.assertContains(day, "Atelier")
        self.assertNotContains(day, "Consulter Makolo Live")
        self.assertEqual(self.client.get(self.live_url).status_code, 404)

    def test_owner_can_opt_into_live_and_beneficiary_can_then_read(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.day_url, {"action": "configure_live", "enabled": "1"},
        )
        self.assertEqual(response.status_code, 302)
        self.occurrence.refresh_from_db()
        self.assertTrue(self.occurrence.live_enabled)

        self.client.force_login(self.beneficiary)
        day = self.client.get(self.day_url)
        self.assertEqual(day.status_code, 200)
        self.assertContains(day, "Consulter Makolo Live")
        live = self.client.get(self.live_url)
        self.assertEqual(live.status_code, 200)
        self.assertContains(live, "Couverture")

    def test_beneficiary_cannot_publish_live(self):
        self.client.force_login(self.beneficiary)
        response = self.client.post(
            self.day_url, {"action": "configure_live", "enabled": "1"},
        )
        self.assertEqual(response.status_code, 403)
        self.occurrence.refresh_from_db()
        self.assertFalse(self.occurrence.live_enabled)
