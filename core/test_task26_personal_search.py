from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessStatus
from activities.models import ActivityStatus, ActivityVisibility, OccurrenceStatus
from activities.services import create_activity, create_occurrence
from journeys.models import Journey, JourneyStatus, WorkflowKind


User = get_user_model()


class Task26PersonalSearchTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="t26-alice",
            email="t26-alice@example.test",
            password="StrongPass2026!",
        )
        self.bob = User.objects.create_user(
            username="t26-bob",
            email="t26-bob@example.test",
            password="StrongPass2026!",
        )
        self.alice_activity, self.alice_occurrence = self._activity(
            self.alice,
            "Forum Alpha Kolwezi",
        )
        self.bob_activity, self.bob_occurrence = self._activity(
            self.bob,
            "Forum Beta Privé",
        )

    def _activity(self, owner, title):
        activity = create_activity(
            created_by=owner,
            owner_profile=owner,
            title=title,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        occurrence = create_occurrence(
            activity=activity,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        return activity, occurrence

    def test_journey_search_starts_from_current_participant_scope(self):
        Journey.objects.create(
            initiated_by=self.alice,
            beneficiary=self.alice,
            activity=self.alice_activity,
            occurrence=self.alice_occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.DRAFT,
        )
        Journey.objects.create(
            initiated_by=self.bob,
            beneficiary=self.bob,
            activity=self.bob_activity,
            occurrence=self.bob_occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.DRAFT,
        )
        self.client.force_login(self.alice)
        response = self.client.get(reverse("core:participant-journeys"), {"q": "Forum"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forum Alpha Kolwezi")
        self.assertNotContains(response, "Forum Beta Privé")

    def test_journey_payment_filter_keeps_t23_active_projection(self):
        Journey.objects.create(
            initiated_by=self.alice,
            beneficiary=self.alice,
            activity=self.alice_activity,
            occurrence=self.alice_occurrence,
            workflow=WorkflowKind.PURCHASE,
            status=JourneyStatus.PENDING_PAYMENT,
        )
        other_activity, other_occurrence = self._activity(self.alice, "Démarche en attente")
        Journey.objects.create(
            initiated_by=self.alice,
            beneficiary=self.alice,
            activity=other_activity,
            occurrence=other_occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.SUBMITTED,
        )
        self.client.force_login(self.alice)
        response = self.client.get(
            reverse("core:participant-journeys"),
            {"status": "payment"},
        )
        self.assertContains(response, "Forum Alpha Kolwezi")
        self.assertNotContains(response, "Démarche en attente")

    def test_access_search_does_not_cross_beneficiaries(self):
        Access.objects.create(
            beneficiary=self.alice,
            activity=self.alice_activity,
            occurrence=self.alice_occurrence,
            status=AccessStatus.VALID,
        )
        Access.objects.create(
            beneficiary=self.bob,
            activity=self.bob_activity,
            occurrence=self.bob_occurrence,
            status=AccessStatus.VALID,
        )
        self.client.force_login(self.alice)
        response = self.client.get(reverse("core:participant-accesses"), {"q": "Forum"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forum Alpha Kolwezi")
        self.assertNotContains(response, "Forum Beta Privé")

    def test_access_history_search_is_canonicalized_to_personal_history(self):
        access = Access.objects.create(
            beneficiary=self.alice,
            activity=self.alice_activity,
            occurrence=self.alice_occurrence,
            status=AccessStatus.USED,
        )
        self.client.force_login(self.alice)
        response = self.client.get(reverse("core:participant-accesses"), {"q": "Kolwezi"})
        self.assertContains(response, "Voir l’historique")
        self.assertNotContains(response, self.alice_activity.title)
        active_ids = {item["access"].pk for item in response.context["active_accesses"]}
        self.assertNotIn(access.pk, active_ids)

        history = self.client.get(
            reverse("core:participant-history"),
            {"q": "Kolwezi", "type": "accesses"},
        )
        self.assertContains(history, self.alice_activity.title)

    def test_journey_list_is_paginated_server_side(self):
        for index in range(26):
            Journey.objects.create(
                initiated_by=self.alice,
                beneficiary=self.alice,
                activity=self.alice_activity,
                occurrence=self.alice_occurrence,
                workflow=WorkflowKind.REGISTRATION,
                status=JourneyStatus.DRAFT,
            )
        self.client.force_login(self.alice)
        response = self.client.get(reverse("core:participant-journeys"))
        self.assertEqual(len(response.context["active_journeys"]), 24)
        self.assertTrue(response.context["active_page_obj"].has_next())
