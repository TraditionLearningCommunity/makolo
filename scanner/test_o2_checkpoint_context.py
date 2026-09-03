from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from operations.models import CheckpointObservation, CheckpointStatus, OccurrenceCheckpoint
from tickets.models import TicketStatus

from .models import ScanResult, ScannerAssignment
from .services import scan_ticket
from .tests import ScannerFixtureMixin


User = get_user_model()


class O2ScannerCheckpointContextTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.owner = User.objects.create_user(username="o2-scan-owner", email="o2-scan-owner@example.test", password="pw")
        self.agent = User.objects.create_user(username="o2-scan-agent", email="o2-scan-agent@example.test", password="pw")
        self.activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O2 Scanner")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="O2 Scanner occurrence",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, hours=1),
        )
        self.checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence,
            key="entry",
            label="Entrée",
        )
        self.other_activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O2 Scanner other")
        self.other_occurrence = Occurrence.objects.create(
            activity=self.other_activity,
            label="Other occurrence",
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=1),
        )

    def test_legacy_assignment_without_checkpoint_remains_valid(self):
        assignment = ScannerAssignment.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            agent=self.agent,
            assigned_by=self.owner,
        )
        self.assertIsNone(assignment.checkpoint_id)

    def test_checkpoint_can_supply_occurrence_and_activity_context(self):
        assignment = ScannerAssignment.objects.create(
            checkpoint=self.checkpoint,
            agent=self.agent,
            assigned_by=self.owner,
        )
        self.assertEqual(assignment.activity_id, self.activity.pk)
        self.assertEqual(assignment.occurrence_id, self.occurrence.pk)

    def test_cross_activity_checkpoint_is_rejected(self):
        assignment = ScannerAssignment(
            activity=self.other_activity,
            occurrence=self.other_occurrence,
            checkpoint=self.checkpoint,
            agent=self.agent,
            assigned_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            assignment.full_clean()


class O2ScannerCheckpointFlowTests(ScannerFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        occurrence = self.event.primary_occurrence
        self.checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=occurrence,
            key="access-control",
            label="Contrôle accès",
            status=CheckpointStatus.OPEN,
        )
        self.assignment.checkpoint = self.checkpoint
        self.assignment.occurrence = occurrence
        self.assignment.activity = occurrence.activity
        self.assignment.save()

    def test_accepted_access_scan_creates_linked_checkpoint_observation(self):
        outcome = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="o2-checkpoint-accepted",
        )
        self.assertTrue(outcome.accepted)
        observation = CheckpointObservation.objects.get(checkpoint=self.checkpoint)
        self.assertEqual(observation.profile, self.participant)
        self.assertIsNotNone(observation.access_use_id)
        self.assertEqual(outcome.log.metadata["checkpoint_observation_id"], str(observation.pk))
        self.assertEqual(outcome.log.metadata["access_use_id"], str(observation.access_use_id))

    def test_closed_checkpoint_rejects_before_access_consumption(self):
        self.checkpoint.status = CheckpointStatus.CLOSED
        self.checkpoint.save(update_fields=["status", "updated_at"])
        outcome = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="o2-checkpoint-closed",
        )
        self.ticket.refresh_from_db()
        self.assertEqual(outcome.result, ScanResult.GATE_UNAVAILABLE)
        self.assertEqual(self.ticket.status, TicketStatus.VALID)
        self.assertFalse(CheckpointObservation.objects.filter(checkpoint=self.checkpoint).exists())
