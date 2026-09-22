from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from access.models import AccessStatus
from access.services import issue_access
from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind


class Z6SurfaceBridgeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.now = timezone.now()
        self.owner = User.objects.create_user(
            username="z6-bridge-owner",
            email="z6-bridge-owner@makolo.test",
        )
        self.profile = User.objects.create_user(
            username="z6-bridge-profile",
            email="z6-bridge-profile@makolo.test",
        )
        self.other = User.objects.create_user(
            username="z6-bridge-other",
            email="z6-bridge-other@makolo.test",
        )
        self.activity = Activity.objects.create(
            title="Bridge Z6",
            created_by=self.owner,
            owner_profile=self.owner,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now + timedelta(hours=4),
            end_at=self.now + timedelta(hours=6),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.profile,
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.access = issue_access(
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            status=AccessStatus.VALID,
            source_key="z6:bridge",
        )

    def test_ongoing_bridges_to_access_history_and_day_of(self):
        self.client.force_authenticate(self.profile)
        response = self.client.get("/api/v1/me/ongoing/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(data["links"]["accesses"], "/api/v1/me/accesses/")
        self.assertEqual(data["links"]["history"], "/api/v1/me/history/")
        access_item = next(
            row for row in data["items"]
            if row["kind"] == "access" and row["source"]["id"] == str(self.access.pk)
        )
        self.assertEqual(
            access_item["links"]["day_of"],
            f"/api/v1/me/occurrences/{self.occurrence.pk}/day-of/",
        )
        self.assertIn("open_day_of", access_item["capabilities"])

    def test_journey_detail_bridges_to_day_of_before_live_phase(self):
        self.client.force_authenticate(self.profile)
        response = self.client.get(f"/api/v1/me/journeys/{self.journey.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(
            data["links"]["day_of"],
            f"/api/v1/me/occurrences/{self.occurrence.pk}/day-of/",
        )
        self.assertIn("open_day_of", data["capabilities"])

    def test_access_detail_day_of_is_only_for_real_beneficiary(self):
        self.client.force_authenticate(self.profile)
        mine = self.client.get(f"/api/v1/me/accesses/{self.access.pk}/")
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(
            mine.json()["data"]["links"]["day_of"],
            f"/api/v1/me/occurrences/{self.occurrence.pk}/day-of/",
        )

        foreign_journey = Journey.objects.create(
            initiated_by=self.profile,
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.PURCHASE,
            status=JourneyStatus.CONFIRMED,
        )
        from commerce.models import CommerceOrder, PaymentMode
        from decimal import Decimal
        CommerceOrder.objects.create(
            journey=foreign_journey,
            buyer=self.profile,
            payment_mode=PaymentMode.NONE,
            currency="USD",
            subtotal=Decimal("0"),
            discount_total=Decimal("0"),
            total=Decimal("0"),
        )
        foreign_access = issue_access(
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=foreign_journey,
            status=AccessStatus.VALID,
            source_key="z6:bridge:other",
        )
        bought = self.client.get(f"/api/v1/me/accesses/{foreign_access.pk}/")
        self.assertEqual(bought.status_code, 200)
        self.assertNotIn("day_of", bought.json()["data"]["links"])
        self.assertNotIn("open_day_of", bought.json()["data"]["capabilities"])

    def test_occurrence_detail_uses_day_of_as_personal_root_and_keeps_live_owner(self):
        self.client.force_authenticate(self.profile)
        response = self.client.get(f"/api/v1/occurrences/{self.occurrence.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(
            data["links"]["day_of"],
            f"/api/v1/me/occurrences/{self.occurrence.pk}/day-of/",
        )
        self.assertIn("open_day_of", data["capabilities"])
        self.assertEqual(
            data["links"]["live"],
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/live/",
        )

    def test_outsider_occurrence_detail_never_gets_personal_day_of_link(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(f"/api/v1/occurrences/{self.occurrence.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("day_of", response.json()["data"]["links"])
