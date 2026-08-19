from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessCredential, AccessStatus
from activities.models import Activity, ActivityStatus, Occurrence, OccurrencePlace, OccurrenceStatus
from geography.models import Place
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .participant_presentation import access_status_label, journey_status_label, next_participant_action
from .participant_selectors import participant_accesses, participant_journeys


User = get_user_model()


class ParticipantExperienceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="participant@example.test", password="secret-test-password")
        self.other = User.objects.create_user(username="other@example.test", password="secret-test-password")
        self.activity = Activity.objects.create(
            title="Atelier communautaire",
            created_by=self.user,
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=2),
            timezone="Africa/Kinshasa",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.place = Place.objects.create(name="Maison des initiatives", locality="Kinshasa")
        OccurrencePlace.objects.create(occurrence=self.occurrence, place=self.place, role="primary")
        self.journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.access = Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            status=AccessStatus.VALID,
        )
        AccessCredential.objects.create(access=self.access)

    def test_non_event_activity_is_visible_without_ticket_models(self):
        self.assertFalse(hasattr(self.activity, "event_vertical"))
        self.assertEqual(list(participant_journeys(self.user)), [self.journey])
        self.assertEqual(list(participant_accesses(self.user)), [self.access])

    def test_centralized_labels_and_next_action(self):
        self.assertEqual(journey_status_label(JourneyStatus.PENDING_APPROVAL), "En attente de validation")
        self.assertEqual(access_status_label(AccessStatus.TRANSFERRED), "Transféré")
        self.journey.status = JourneyStatus.PENDING_PAYMENT
        self.assertEqual(next_participant_action(self.journey), "Payer")

    def test_participant_pages_show_canonical_occurrence_place_and_access(self):
        self.client.force_login(self.user)
        home = self.client.get(reverse("core:participant-home"))
        self.assertContains(home, "Atelier communautaire")
        self.assertContains(home, "Kinshasa")
        detail = self.client.get(reverse("core:participant-journey-detail", kwargs={"pk": self.journey.pk}))
        self.assertContains(detail, "Inscription")
        self.assertContains(detail, "Maison des initiatives")
        access = self.client.get(reverse("core:participant-access-detail", kwargs={"pk": self.access.pk}))
        self.assertContains(access, "Confirmation")
        self.assertContains(access, "data:image/png;base64")

    def test_ownership_hides_other_participant_objects(self):
        self.client.force_login(self.other)
        journey_response = self.client.get(reverse("core:participant-journey-detail", kwargs={"pk": self.journey.pk}))
        access_response = self.client.get(reverse("core:participant-access-detail", kwargs={"pk": self.access.pk}))
        self.assertEqual(journey_response.status_code, 404)
        self.assertEqual(access_response.status_code, 404)
