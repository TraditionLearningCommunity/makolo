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


class Task30PersonalHistoryIATests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="task30-history",
            email="task30-history@example.test",
            password="StrongPass2026!",
        )
        self.activity = create_activity(
            created_by=self.user,
            owner_profile=self.user,
            title="Mémoire canonique T30",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.occurrence = create_occurrence(
            activity=self.activity,
            start_at=timezone.now() - timedelta(days=2),
            end_at=timezone.now() - timedelta(days=2, hours=-2),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.COMPLETED,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
        )
        self.access = Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            status=AccessStatus.USED,
        )
        self.client.force_login(self.user)

    def test_journeys_surface_links_to_canonical_history_without_relisting_past(self):
        response = self.client.get(reverse("core:participant-journeys"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Voir l’historique")
        self.assertNotContains(response, "Mémoire canonique T30")

    def test_accesses_surface_links_to_canonical_history_without_relisting_past(self):
        response = self.client.get(reverse("core:participant-accesses"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Voir l’historique")
        self.assertNotContains(response, "Mémoire canonique T30")

    def test_canonical_history_keeps_the_past_visible_once(self):
        response = self.client.get(reverse("core:participant-history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mémoire canonique T30")
