from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import AccessStatus, AccessUseResult
from access.services import issue_access, render_access_credential, validate_access_credential
from activities.models import Activity, Occurrence
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .participant_selectors import (
    participant_access_history,
    participant_active_accesses,
    participant_active_journeys,
    participant_history_journeys,
)


User = get_user_model()


class ParticipantLifecycleTests(TestCase):
    def setUp(self):
        self.participant = User.objects.create_user(
            username="task23-participant",
            email="task23-participant@example.com",
            password="Task23-2026!",
        )
        self.other = User.objects.create_user(
            username="task23-other",
            email="task23-other@example.com",
            password="Task23-2026!",
        )
        self.activity = Activity.objects.create(
            created_by=self.participant,
            title="Atelier canonique Task 23",
        )
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=now - timedelta(minutes=30),
            end_at=now + timedelta(hours=2),
        )

    def journey(self, *, status=JourneyStatus.PENDING_PAYMENT, workflow=WorkflowKind.REGISTRATION):
        return Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=workflow,
            status=status,
        )

    def test_journey_with_remaining_action_stays_in_mes_demarches(self):
        journey = self.journey(status=JourneyStatus.PENDING_PAYMENT)
        self.assertIn(journey, participant_active_journeys(self.participant))
        self.assertNotIn(journey, participant_history_journeys(self.participant))

    def test_confirmed_journey_that_produced_access_moves_out_of_active_journeys(self):
        journey = self.journey(status=JourneyStatus.CONFIRMED)
        access = issue_access(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=journey,
            source_key="task23:projection",
        )
        self.assertNotIn(journey, participant_active_journeys(self.participant))
        self.assertIn(journey, participant_history_journeys(self.participant))
        self.assertIn(access, participant_active_accesses(self.participant))

    def test_used_access_is_history_not_active_and_control_history_is_visible(self):
        journey = self.journey(status=JourneyStatus.CONFIRMED)
        access = issue_access(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=journey,
            source_key="task23:used",
        )
        credential = access.credentials.get()
        outcome = validate_access_credential(
            render_access_credential(credential),
            expected_activity=self.activity,
            expected_occurrence=self.occurrence,
        )
        self.assertEqual(outcome.result, AccessUseResult.ACCEPTED)
        access.refresh_from_db()
        self.assertEqual(access.status, AccessStatus.USED)
        self.assertNotIn(access, participant_active_accesses(self.participant))
        self.assertIn(access, participant_access_history(self.participant))

        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:participant-access-detail", kwargs={"pk": access.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Historique de contrôle")
        self.assertContains(response, "Accès accepté")
        self.assertNotContains(response, "client_reference")
        self.assertNotContains(response, "credential")

    def test_expired_revoked_cancelled_accesses_are_history(self):
        for index, status in enumerate(
            (AccessStatus.EXPIRED, AccessStatus.REVOKED, AccessStatus.CANCELLED),
            start=1,
        ):
            access = issue_access(
                beneficiary=self.participant,
                activity=self.activity,
                occurrence=None,
                status=status,
                valid_from=None,
                valid_until=None,
                source_key=f"task23:history:{index}",
                create_credential=False,
            )
            self.assertIn(access, participant_access_history(self.participant))
            self.assertNotIn(access, participant_active_accesses(self.participant))

    def test_participant_cannot_read_another_participants_access_or_history(self):
        foreign = issue_access(
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.occurrence,
            source_key="task23:foreign",
        )
        token = render_access_credential(foreign.credentials.get())
        validate_access_credential(
            token,
            expected_activity=self.activity,
            expected_occurrence=self.occurrence,
        )

        self.client.force_login(self.participant)
        response = self.client.get(reverse("core:participant-access-detail", kwargs={"pk": foreign.pk}))
        self.assertEqual(response.status_code, 404)

    def test_activity_without_event_uses_same_participant_access_flow(self):
        self.assertFalse(hasattr(self.activity, "event_vertical"))
        access = issue_access(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            source_key="task23:non-event",
        )
        self.assertIn(access, participant_active_accesses(self.participant))
