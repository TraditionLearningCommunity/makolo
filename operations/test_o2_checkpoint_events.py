from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .checkpoint_services import (
    assign_checkpoint_operator,
    end_checkpoint_assignment,
    observe_checkpoint,
    open_checkpoint,
)
from .models import CheckpointAssignment, OccurrenceCheckpoint


User = get_user_model()


class O2CheckpointHistoryAndEventTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.owner = User.objects.create_user(username="o2-event-owner", email="o2-event-owner@example.test", password="pw")
        self.manager = User.objects.create_user(username="o2-event-manager", email="o2-event-manager@example.test", password="pw")
        self.operator = User.objects.create_user(username="o2-event-operator", email="o2-event-operator@example.test", password="pw")
        self.participant = User.objects.create_user(
            username="o2-event-participant",
            email="o2-event-participant@example.test",
            password="pw",
            first_name="O2",
            last_name="Participant",
        )
        self.activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O2 Events")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="O2 Events occurrence",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, hours=1),
        )
        grant_activity_role(
            profile=self.manager,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o2-event-test",
        )
        Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence,
            key="welcome",
            label="Accueil",
        )

    def test_assignment_end_preserves_history_and_allows_reassignment(self):
        first = assign_checkpoint_operator(actor=self.manager, checkpoint=self.checkpoint, profile=self.operator)
        ended = end_checkpoint_assignment(actor=self.manager, assignment=first)
        self.assertIsNotNone(ended.ended_at)
        second = assign_checkpoint_operator(actor=self.manager, checkpoint=self.checkpoint, profile=self.operator)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(
            CheckpointAssignment.objects.filter(checkpoint=self.checkpoint, profile=self.operator).count(),
            2,
        )
        self.assertEqual(
            CheckpointAssignment.objects.filter(
                checkpoint=self.checkpoint,
                profile=self.operator,
                ended_at__isnull=True,
            ).count(),
            1,
        )

    def test_observed_event_payload_is_minimal_and_non_sensitive(self):
        open_checkpoint(actor=self.manager, checkpoint=self.checkpoint)
        observation = observe_checkpoint(
            actor=self.manager,
            checkpoint=self.checkpoint,
            profile=self.participant,
            source="operator",
            client_reference="o2-event-observation",
        )
        event = DomainEventOutbox.objects.get(
            event_type=DomainEventType.CHECKPOINT_OBSERVED,
            source_id=str(observation.pk),
        )
        self.assertEqual(event.payload["checkpoint_id"], str(self.checkpoint.pk))
        self.assertEqual(event.payload["occurrence_id"], str(self.occurrence.pk))
        self.assertEqual(event.payload["subject_type"], "profile")
        serialized = str(event.payload)
        self.assertNotIn(self.participant.email, serialized)
        self.assertNotIn(self.participant.get_full_name(), serialized)
        self.assertNotIn("credential", serialized.lower())
