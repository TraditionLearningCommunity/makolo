from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessStatus
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from commerce.models import CommerceOrder, PaymentMode
from journeys.models import Journey, JourneyStatus, WorkflowKind
from notifications.models import Notification


User = get_user_model()


class Task29PersonalHubTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="t29-profile",
            email="t29-profile@example.test",
            password="Task29-2026!",
        )
        self.other = User.objects.create_user(
            username="t29-other",
            email="t29-other@example.test",
            password="Task29-2026!",
        )
        self.now = timezone.now()
        self.activity = Activity.objects.create(
            title="Voyage mémoire T29",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now + timedelta(days=2),
            end_at=self.now + timedelta(days=2, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.client.force_login(self.profile)

    def _journey(self, *, status, occurrence=None, activity=None, beneficiary=None):
        return Journey.objects.create(
            initiated_by=self.profile,
            beneficiary=beneficiary or self.profile,
            activity=activity or self.activity,
            occurrence=self.occurrence if occurrence is None else occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=status,
        )

    def test_home_does_not_repeat_upcoming_access_as_second_access_card(self):
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            status=AccessStatus.VALID,
        )
        response = self.client.get(reverse("core:participant-home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["access"].pk for item in response.context["upcoming"]], [access.pk])
        self.assertEqual(response.context["active_access_count"], 1)
        self.assertNotIn("active_accesses", response.context)
        self.assertContains(response, "1 accès actif")

    def test_actionable_journey_is_not_recent_history(self):
        journey = self._journey(status=JourneyStatus.PENDING_PAYMENT)
        CommerceOrder.objects.create(
            journey=journey,
            buyer=self.profile,
            payment_mode=PaymentMode.UPFRONT,
            currency="USD",
            subtotal=Decimal("10.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("10.00"),
        )
        response = self.client.get(reverse("core:participant-home"))
        self.assertIn(journey.pk, [item["journey"].pk for item in response.context["actionable"]])
        recent_journey_ids = {
            item["journey_card"]["journey"].pk
            for item in response.context["recent_history"]
            if item["journey_card"] is not None
        }
        self.assertNotIn(journey.pk, recent_journey_ids)

    def test_history_deduplicates_linked_journey_and_access(self):
        journey = self._journey(status=JourneyStatus.CONFIRMED)
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=journey,
            status=AccessStatus.USED,
        )
        response = self.client.get(reverse("core:participant-history"))
        self.assertEqual(response.status_code, 200)
        matching = [item for item in response.context["history_items"] if item["activity"].pk == self.activity.pk]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["kind"], "access")
        self.assertEqual(matching[0]["access_card"]["access"].pk, access.pk)
        self.assertEqual(matching[0]["journey_card"]["journey"].pk, journey.pk)

    def test_rejected_journey_without_access_is_history(self):
        journey = self._journey(status=JourneyStatus.REJECTED)
        response = self.client.get(reverse("core:participant-history"), {"type": "journeys"})
        ids = [item["journey_card"]["journey"].pk for item in response.context["history_items"]]
        self.assertIn(journey.pk, ids)
        self.assertContains(response, "Demande refusée")

    def test_manual_access_without_journey_is_history(self):
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            status=AccessStatus.USED,
        )
        response = self.client.get(reverse("core:participant-history"), {"type": "accesses"})
        ids = [item["access_card"]["access"].pk for item in response.context["history_items"]]
        self.assertIn(access.pk, ids)

    def test_valid_access_for_past_occurrence_moves_to_history(self):
        past = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now - timedelta(days=2),
            end_at=self.now - timedelta(days=1),
            status=OccurrenceStatus.COMPLETED,
        )
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=past,
            status=AccessStatus.VALID,
        )
        home = self.client.get(reverse("core:participant-home"))
        self.assertNotIn(access.pk, [item["access"].pk for item in home.context["upcoming"]])
        history = self.client.get(reverse("core:participant-history"))
        self.assertIn(access.pk, [
            item["access_card"]["access"].pk
            for item in history.context["history_items"]
            if item["kind"] == "access"
        ])

    def test_buyer_does_not_get_beneficiary_participation_in_personal_history(self):
        journey = Journey.objects.create(
            initiated_by=self.profile,
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.PURCHASE,
            status=JourneyStatus.CONFIRMED,
        )
        CommerceOrder.objects.create(
            journey=journey,
            buyer=self.profile,
            payment_mode=PaymentMode.NONE,
            currency="USD",
            subtotal=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("0.00"),
        )
        access = Access.objects.create(
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=journey,
            status=AccessStatus.USED,
        )
        response = self.client.get(reverse("core:participant-history"))
        history_access_ids = {
            item["access_card"]["access"].pk
            for item in response.context["history_items"]
            if item["kind"] == "access"
        }
        self.assertNotIn(access.pk, history_access_ids)
        bought = self.client.get(reverse("core:participant-accesses"))
        self.assertIn(access.pk, [item["access"].pk for item in bought.context["purchased_for_others"]])

    def test_history_is_paginated(self):
        for index in range(27):
            activity = Activity.objects.create(
                title=f"Historique T29 {index:02d}",
                created_by=self.other,
                owner_profile=self.other,
                status=ActivityStatus.PUBLISHED,
            )
            Journey.objects.create(
                initiated_by=self.profile,
                beneficiary=self.profile,
                activity=activity,
                workflow=WorkflowKind.REGISTRATION,
                status=JourneyStatus.REJECTED,
            )
        first = self.client.get(reverse("core:participant-history"), {"type": "journeys"})
        second = self.client.get(reverse("core:participant-history"), {"type": "journeys", "page": 2})
        self.assertEqual(len(first.context["history_items"]), 24)
        self.assertTrue(first.context["page_obj"].has_next())
        self.assertGreater(len(second.context["history_items"]), 0)

    def test_personal_navigation_uses_history_and_bell_for_notifications(self):
        notification = Notification.objects.create(
            recipient=self.profile,
            title="Action test T29",
            message="Ne doit pas être marquée lue par le hub.",
        )
        response = self.client.get(reverse("core:participant-home"))
        self.assertContains(response, reverse("core:participant-history"))
        self.assertContains(response, reverse("notifications:list"))
        self.assertNotContains(response, ">Notifications</span>")
        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)

    def test_hub_shortcuts_reuse_canonical_surfaces(self):
        response = self.client.get(reverse("core:participant-home"))
        self.assertContains(response, reverse("groups:list"))
        self.assertContains(response, reverse("discovery:bookmarks"))
        self.assertContains(response, reverse("organizations:list"))

    def test_hub_query_count_does_not_scale_with_recent_history_rows(self):
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(reverse("core:participant-home"))
        for index in range(8):
            activity = Activity.objects.create(
                title=f"Mémoire bornée {index}",
                created_by=self.other,
                owner_profile=self.other,
            )
            Access.objects.create(
                beneficiary=self.profile,
                activity=activity,
                status=AccessStatus.USED,
            )
        with CaptureQueriesContext(connection) as populated:
            self.client.get(reverse("core:participant-home"))
        self.assertLessEqual(len(populated), len(baseline) + 3)
