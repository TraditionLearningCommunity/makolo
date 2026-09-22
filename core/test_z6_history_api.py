from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from access.models import Access, AccessCredential, AccessStatus, AccessUse, AccessUseResult
from access.services import render_access_credential
from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from commerce.models import CommerceOrder, PaymentMode
from journeys.models import Journey, JourneyStatus, WorkflowKind
from notifications.models import Notification


PASSWORD = "Makolo!2026-Z6-HistoryA7"


class Z6PersonalHistoryAPIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = self._user("z6-history-owner")
        self.other = self._user("z6-history-other")
        self.now = timezone.now()
        self.activity = Activity.objects.create(
            title="Mémoire Z6",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        self.future_occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now + timedelta(days=2),
            end_at=self.now + timedelta(days=2, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.past_occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now - timedelta(days=2),
            end_at=self.now - timedelta(days=2) + timedelta(hours=2),
            status=OccurrenceStatus.COMPLETED,
        )

    def _user(self, username):
        return User.objects.create_user(
            username=username,
            email=f"{username}@makolo.test",
            password=PASSWORD,
        )

    def _journey(self, *, status, beneficiary=None, activity=None, fulfilled_at=None):
        return Journey.objects.create(
            initiated_by=self.owner,
            beneficiary=beneficiary or self.owner,
            activity=activity or self.activity,
            occurrence=self.past_occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=status,
            fulfilled_at=fulfilled_at,
        )

    def test_history_requires_authentication_and_rejects_profile_override(self):
        response = self.client.get("/api/v1/me/history/")
        self.assertEqual(response.status_code, 401)

        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/v1/me/history/?profile_id={self.other.pk}"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_empty_history_is_stable_and_private(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/history/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["meta"]["projection"], "personal.history")
        self.assertEqual(payload["data"]["items"], [])
        self.assertEqual(payload["data"]["page"]["count"], 0)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_active_journey_and_current_access_stay_out_of_history(self):
        self._journey(status=JourneyStatus.PENDING_PAYMENT)
        Access.objects.create(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.future_occurrence,
            status=AccessStatus.VALID,
        )

        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/history/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["items"], [])

    def test_history_contains_completed_journey_and_historical_access(self):
        completed_activity = Activity.objects.create(
            title="Démarche accomplie Z6",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        journey = Journey.objects.create(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=completed_activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
            fulfilled_at=self.now - timedelta(hours=4),
        )
        used = Access.objects.create(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.past_occurrence,
            status=AccessStatus.USED,
        )
        AccessUse.objects.create(
            access=used,
            result=AccessUseResult.ACCEPTED,
            used_at=self.now - timedelta(hours=2),
        )

        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/history/")
        self.assertEqual(response.status_code, 200)

        rows = response.json()["data"]["items"]
        refs = {(row["kind"], row["source"]["id"]) for row in rows}
        self.assertIn(("journey", str(journey.pk)), refs)
        self.assertIn(("access", str(used.pk)), refs)

    def test_linked_journey_and_access_are_one_history_experience(self):
        journey = self._journey(
            status=JourneyStatus.FULFILLED,
            fulfilled_at=self.now - timedelta(hours=3),
        )
        access = Access.objects.create(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.past_occurrence,
            journey=journey,
            status=AccessStatus.USED,
        )
        AccessUse.objects.create(
            access=access,
            result=AccessUseResult.ACCEPTED,
            used_at=self.now - timedelta(hours=2),
        )

        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/history/")
        rows = [
            row
            for row in response.json()["data"]["items"]
            if row["activity"]["id"] == str(self.activity.pk)
        ]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "access")
        self.assertEqual(rows[0]["source"]["id"], str(access.pk))

    def test_business_timestamp_orders_journeys_not_updated_at(self):
        older = self._journey(
            status=JourneyStatus.FULFILLED,
            fulfilled_at=self.now - timedelta(days=5),
        )
        newer = self._journey(
            status=JourneyStatus.FULFILLED,
            fulfilled_at=self.now - timedelta(days=1),
        )
        Journey.objects.filter(pk=older.pk).update(updated_at=self.now)
        Journey.objects.filter(pk=newer.pk).update(
            updated_at=self.now - timedelta(days=10)
        )

        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/history/?type=journeys")
        ids = [row["source"]["id"] for row in response.json()["data"]["items"]]

        self.assertLess(ids.index(str(newer.pk)), ids.index(str(older.pk)))
        by_id = {row["source"]["id"]: row for row in response.json()["data"]["items"]}
        self.assertEqual(
            by_id[str(newer.pk)]["occurred_at"],
            newer.fulfilled_at.isoformat(),
        )

    def test_partial_legacy_terminal_journey_falls_back_without_500(self):
        legacy = self._journey(status=JourneyStatus.REJECTED)
        Journey.objects.filter(pk=legacy.pk).update(
            updated_at=self.now - timedelta(days=3)
        )

        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/history/?type=journeys")

        self.assertEqual(response.status_code, 200)
        row = next(
            item
            for item in response.json()["data"]["items"]
            if item["source"]["id"] == str(legacy.pk)
        )
        self.assertEqual(row["outcome"]["code"], JourneyStatus.REJECTED)
        self.assertIsNotNone(row["occurred_at"])

    def test_other_profile_and_buyer_only_facts_never_become_my_history(self):
        foreign = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.past_occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
            fulfilled_at=self.now - timedelta(hours=1),
        )
        bought_journey = Journey.objects.create(
            initiated_by=self.owner,
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.past_occurrence,
            workflow=WorkflowKind.PURCHASE,
            status=JourneyStatus.FULFILLED,
            fulfilled_at=self.now - timedelta(hours=1),
        )
        CommerceOrder.objects.create(
            journey=bought_journey,
            buyer=self.owner,
            payment_mode=PaymentMode.NONE,
            currency="USD",
            subtotal=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("0.00"),
        )
        bought_access = Access.objects.create(
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.past_occurrence,
            journey=bought_journey,
            status=AccessStatus.USED,
        )

        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/history/")
        rendered = str(response.json())

        self.assertNotIn(str(foreign.pk), rendered)
        self.assertNotIn(str(bought_journey.pk), rendered)
        self.assertNotIn(str(bought_access.pk), rendered)
        self.assertNotIn(self.other.email, rendered)

    def test_history_never_serializes_credentials_or_notifications(self):
        access = Access.objects.create(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.past_occurrence,
            status=AccessStatus.USED,
        )
        credential = AccessCredential.objects.create(access=access)
        AccessUse.objects.create(
            access=access,
            credential=credential,
            result=AccessUseResult.ACCEPTED,
            used_at=self.now - timedelta(hours=1),
        )
        notification = Notification.objects.create(
            recipient=self.owner,
            title="TRACE-TECHNIQUE-Z6",
            message="Ne doit pas devenir un fait historique.",
        )

        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/history/")
        rendered = str(response.json())

        self.assertNotIn(str(credential.public_id), rendered)
        self.assertNotIn(render_access_credential(credential), rendered)
        self.assertNotIn(notification.title, rendered)
        self.assertNotIn("credential", rendered.lower())
        self.assertNotIn("notification", rendered.lower())
        self.assertNotIn("domain_event", rendered.lower())

    def test_filters_search_and_pagination_are_stable(self):
        for index in range(28):
            activity = Activity.objects.create(
                title=f"Archive Z6 {index:02d}",
                created_by=self.other,
                owner_profile=self.other,
                status=ActivityStatus.PUBLISHED,
            )
            journey = Journey.objects.create(
                initiated_by=self.owner,
                beneficiary=self.owner,
                activity=activity,
                workflow=WorkflowKind.REGISTRATION,
                status=JourneyStatus.REJECTED,
            )
            Journey.objects.filter(pk=journey.pk).update(
                updated_at=self.now - timedelta(minutes=index)
            )

        self.client.force_authenticate(self.owner)
        first = self.client.get(
            "/api/v1/me/history/?type=journeys&q=Archive&limit=10&offset=0"
        )
        second = self.client.get(
            "/api/v1/me/history/?type=journeys&q=Archive&limit=10&offset=10"
        )
        repeat = self.client.get(
            "/api/v1/me/history/?type=journeys&q=Archive&limit=10&offset=0"
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["data"]["page"]["count"], 28)
        first_ids = [row["source"]["id"] for row in first.json()["data"]["items"]]
        second_ids = [row["source"]["id"] for row in second.json()["data"]["items"]]
        repeat_ids = [row["source"]["id"] for row in repeat.json()["data"]["items"]]
        self.assertEqual(first_ids, repeat_ids)
        self.assertTrue(set(first_ids).isdisjoint(second_ids))

        invalid = self.client.get("/api/v1/me/history/?limit=51")
        self.assertEqual(invalid.status_code, 400)
        invalid_type = self.client.get("/api/v1/me/history/?type=events")
        self.assertEqual(invalid_type.status_code, 400)

    def test_moi_links_to_history_without_embedding_the_collection(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/v1/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["links"]["history"],
            "/api/v1/me/history/",
        )
        self.assertNotIn("history", response.json()["data"])
