from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessCredential, AccessStatus
from access.services import issue_access, render_access_credential, revoke_access
from activities.models import (
    Activity,
    Occurrence,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
    OccurrenceTimingKind,
)
from geography.models import Place
from journeys.models import Journey, JourneyStatus, WorkflowKind


User = get_user_model()


class M8CJourneyOccurrenceActionWebTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(username="m8c-owner", email="m8c-owner@example.test", password="pw")
        self.participant = User.objects.create_user(username="m8c-participant", email="m8c-participant@example.test", password="pw")
        self.outsider = User.objects.create_user(username="m8c-outsider", email="m8c-outsider@example.test", password="pw")
        self.activity = Activity.objects.create(created_by=self.owner, owner_profile=self.owner, title="Atelier M8-C")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Session principale",
            start_at=self.now + timedelta(hours=4),
            end_at=self.now + timedelta(hours=6),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.place = Place.objects.create(
            name="Maison Makolo",
            address_line="12 avenue Action",
            locality="Lubumbashi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
            access_instructions="Présentez-vous à l’accueil.",
            latitude="-11.664700",
            longitude="27.479400",
            created_by=self.owner,
        )
        OccurrencePlace.objects.create(
            occurrence=self.occurrence,
            place=self.place,
            role=OccurrencePlaceRole.PRIMARY,
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
        self.credential = AccessCredential.objects.create(access=self.access)

    def test_ready_journey_is_calm_and_hands_off_to_occurrence(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:participant-journey-detail", args=[self.journey.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Est-ce que tout est prêt ?")
        self.assertContains(response, "Tout est prêt.")
        self.assertContains(response, "Vous n’avez rien d’autre à préparer maintenant.")
        self.assertContains(response, "Voir les informations pratiques")
        self.assertContains(response, reverse("core:participant-occurrence-live", args=[self.occurrence.pk]))

    def test_journey_direct_idor_is_hidden(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("core:participant-journey-detail", args=[self.journey.pk]))
        self.assertEqual(response.status_code, 404)

    def test_pending_access_is_waiting_not_presented_as_user_action(self):
        revoke_access(access=self.access)
        self.access = issue_access(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            status=AccessStatus.PENDING,
            source_key="m8c:web:pending",
            create_credential=False,
        )
        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:participant-journey-detail", args=[self.journey.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "En attente.")
        self.assertContains(response, "Le droit d’accès est en préparation.")
        self.assertContains(response, "En attente de quelqu’un d’autre")

    def test_participant_live_page_is_safe_and_action_oriented(self):
        self.occurrence.start_at = self.now - timedelta(minutes=5)
        self.occurrence.end_at = self.now + timedelta(hours=2)
        self.occurrence.save(update_fields=["start_at", "end_at", "updated_at"])
        token = render_access_credential(self.credential)
        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:participant-occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ce qui compte maintenant")
        self.assertContains(response, "Votre accès est prêt")
        self.assertContains(response, "Maison Makolo")
        rendered = response.content.decode()
        self.assertNotIn(token, rendered)
        self.assertNotIn("AccessCredential", rendered)

    def test_live_direct_idor_is_hidden(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("core:participant-occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cancelled_occurrence_has_no_stale_live_instruction(self):
        self.occurrence.status = OccurrenceStatus.CANCELLED
        self.occurrence.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:participant-occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cette activité est annulée")
        self.assertContains(response, "Ne vous déplacez pas")
        self.assertNotContains(response, "Rejoignez")

    def test_date_only_live_surface_never_renders_fake_midnight(self):
        target = (self.now + timedelta(days=3)).date()
        self.occurrence.timing_kind = OccurrenceTimingKind.DATE_ONLY
        self.occurrence.start_at = None
        self.occurrence.end_at = None
        self.occurrence.start_date = target
        self.occurrence.start_time = None
        self.occurrence.end_date = target
        self.occurrence.end_time = None
        self.occurrence.save(
            update_fields=[
                "timing_kind",
                "start_at",
                "end_at",
                "start_date",
                "start_time",
                "end_date",
                "end_time",
                "updated_at",
            ]
        )
        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:participant-occurrence-live", args=[self.occurrence.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Heure à confirmer")
        self.assertNotContains(response, "00:00")
