from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from core.models import DomainEventOutbox
from journeys.models import Journey, JourneyStatus, WorkflowKind
from readiness import ReadinessCheck, ReadinessCheckState, ReadinessStatus, reduce_readiness_status

from .models import (
    CheckpointAssignment,
    CheckpointStatus,
    OccurrenceCheckpoint,
    OccurrenceQueue,
    PlacementPlan,
    QueueStatus,
)
from .operational_readiness import resolve_operational_readiness


User = get_user_model()


class O4OperationalReadinessTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(username="o4-ready-owner", email="o4-ready-owner@example.test", password="pw")
        self.participant = User.objects.create_user(username="o4-ready-participant", email="o4-ready-participant@example.test", password="pw")
        self.operator = User.objects.create_user(username="o4-ready-operator", email="o4-ready-operator@example.test", password="pw")
        self.activity = Activity.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="O4 readiness",
        )

    def occurrence(self, **overrides):
        values = {
            "activity": self.activity,
            "label": "O4 live",
            "start_at": self.now - timedelta(minutes=10),
            "end_at": self.now + timedelta(hours=2),
            "status": OccurrenceStatus.SCHEDULED,
        }
        values.update(overrides)
        return Occurrence.objects.create(**values)

    def journey(self, occurrence):
        return Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )

    def test_reducer_preserves_existing_precedence_and_ignores_not_applicable(self):
        ready = ReadinessCheck("ready", "test", ReadinessCheckState.SATISFIED, False, "ready", "ready")
        na = ReadinessCheck("na", "test", ReadinessCheckState.NOT_APPLICABLE, False, "na", "na")
        warning = ReadinessCheck("warning", "test", ReadinessCheckState.ACTION_REQUIRED, False, "warning", "warning")
        blocked = ReadinessCheck("blocked", "test", ReadinessCheckState.BLOCKING, True, "blocked", "blocked")
        self.assertEqual(reduce_readiness_status([ready, na]), ReadinessStatus.READY)
        self.assertEqual(reduce_readiness_status([ready, warning]), ReadinessStatus.ACTION_REQUIRED)
        self.assertEqual(reduce_readiness_status([warning, blocked]), ReadinessStatus.BLOCKED)

    def test_cancelled_and_completed_occurrences_are_explained_without_persistence(self):
        cancelled = self.occurrence(status=OccurrenceStatus.CANCELLED)
        before = DomainEventOutbox.objects.count()
        result = resolve_operational_readiness(cancelled, observed_at=self.now)
        self.assertEqual(result.status, ReadinessStatus.BLOCKED)
        self.assertTrue(any(check.reason_code == "occurrence_cancelled" for check in result.blocking_items))
        self.assertEqual(DomainEventOutbox.objects.count(), before)

        completed = self.occurrence(status=OccurrenceStatus.COMPLETED)
        self.assertEqual(
            resolve_operational_readiness(completed, observed_at=self.now).status,
            ReadinessStatus.COMPLETE,
        )

    def test_required_placement_is_not_invented_when_unused_and_blocks_only_when_required(self):
        occurrence = self.occurrence()
        self.journey(occurrence)
        unused = resolve_operational_readiness(occurrence, observed_at=self.now)
        placement = next(check for check in unused.checks if check.key == "operations.placement")
        self.assertEqual(placement.state, ReadinessCheckState.NOT_APPLICABLE)

        PlacementPlan.objects.create(occurrence=occurrence, key="bus", label="Bus", required=True)
        result = resolve_operational_readiness(occurrence, observed_at=self.now)
        self.assertEqual(result.status, ReadinessStatus.BLOCKED)
        self.assertTrue(any(check.reason_code == "required_placement_incomplete" for check in result.blocking_items))

    def test_required_checkpoint_closed_blocks_and_paused_warns(self):
        occurrence = self.occurrence()
        closed = OccurrenceCheckpoint.objects.create(
            occurrence=occurrence,
            key="boarding",
            label="Embarquement",
            required=True,
            status=CheckpointStatus.CLOSED,
        )
        result = resolve_operational_readiness(occurrence, observed_at=self.now)
        self.assertEqual(result.status, ReadinessStatus.BLOCKED)
        check = next(check for check in result.checks if check.key == f"operations.checkpoints.{closed.pk}")
        self.assertEqual(check.reason_code, "required_checkpoint_closed")

        closed.status = CheckpointStatus.PAUSED
        closed.save(update_fields=["status", "updated_at"])
        warning = resolve_operational_readiness(occurrence, observed_at=self.now)
        self.assertEqual(warning.status, ReadinessStatus.ACTION_REQUIRED)
        self.assertTrue(any(check.reason_code == "required_checkpoint_paused" for check in warning.action_items))

    def test_assignment_never_grants_authority(self):
        occurrence = self.occurrence()
        checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=occurrence,
            key="boarding",
            label="Embarquement",
            required=True,
            status=CheckpointStatus.OPEN,
        )
        CheckpointAssignment.objects.create(checkpoint=checkpoint, profile=self.operator, assigned_by=self.owner)
        result = resolve_operational_readiness(occurrence, observed_at=self.now)
        self.assertEqual(result.status, ReadinessStatus.BLOCKED)
        self.assertTrue(any(check.reason_code == "assigned_operator_without_effective_authority" for check in result.blocking_items))

        checkpoint.status = CheckpointStatus.PAUSED
        checkpoint.save(update_fields=["status", "updated_at"])
        paused = resolve_operational_readiness(occurrence, observed_at=self.now)
        self.assertEqual(paused.status, ReadinessStatus.ACTION_REQUIRED)
        self.assertTrue(any(check.reason_code == "assigned_operator_without_effective_authority" for check in paused.action_items))

        checkpoint.status = CheckpointStatus.OPEN
        checkpoint.save(update_fields=["status", "updated_at"])
        grant_activity_role(
            profile=self.operator,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o4-readiness-test",
        )
        authorized = resolve_operational_readiness(occurrence, observed_at=self.now)
        authority = next(check for check in authorized.checks if check.key == "operations.authority")
        self.assertEqual(authority.state, ReadinessCheckState.SATISFIED)

    def test_authority_is_evaluated_per_open_checkpoint(self):
        occurrence = self.occurrence()
        authorized_operator = User.objects.create_user(
            username="o4-ready-authorized-operator",
            email="o4-ready-authorized-operator@example.test",
            password="pw",
        )
        grant_activity_role(
            profile=authorized_operator,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o4-readiness-mixed-authority-test",
        )
        unauthorized_checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=occurrence,
            key="boarding-a",
            label="Embarquement A",
            required=True,
            status=CheckpointStatus.OPEN,
            position=1,
        )
        authorized_checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=occurrence,
            key="boarding-b",
            label="Embarquement B",
            required=True,
            status=CheckpointStatus.OPEN,
            position=2,
        )
        CheckpointAssignment.objects.create(
            checkpoint=unauthorized_checkpoint,
            profile=self.operator,
            assigned_by=self.owner,
        )
        CheckpointAssignment.objects.create(
            checkpoint=authorized_checkpoint,
            profile=authorized_operator,
            assigned_by=self.owner,
        )

        result = resolve_operational_readiness(occurrence, observed_at=self.now)
        self.assertEqual(result.status, ReadinessStatus.BLOCKED)
        self.assertTrue(any(check.reason_code == "assigned_operator_without_effective_authority" for check in result.blocking_items))

    def test_queue_is_not_applicable_when_unused_and_paused_is_explicit(self):
        occurrence = self.occurrence()
        unused = resolve_operational_readiness(occurrence, observed_at=self.now)
        queue = next(check for check in unused.checks if check.key == "operations.queue")
        self.assertEqual(queue.state, ReadinessCheckState.NOT_APPLICABLE)

        OccurrenceQueue.objects.create(occurrence=occurrence, key="boarding", label="Embarquement", status=QueueStatus.PAUSED)
        result = resolve_operational_readiness(occurrence, observed_at=self.now)
        self.assertEqual(result.status, ReadinessStatus.ACTION_REQUIRED)
        self.assertTrue(any(check.reason_code == "queue_paused" for check in result.action_items))

    def test_capacity_is_not_applicable_when_unused_and_overcommit_blocks(self):
        occurrence = self.occurrence()
        journey = self.journey(occurrence)
        unused = resolve_operational_readiness(occurrence, observed_at=self.now)
        capacity = next(check for check in unused.checks if check.key == "operations.capacity")
        self.assertEqual(capacity.state, ReadinessCheckState.NOT_APPLICABLE)

        pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=occurrence,
            label="Bus",
            total_quantity=1,
        )
        CapacityReservation.objects.create(
            pool=pool,
            journey=journey,
            quantity=2,
            status=CapacityReservationStatus.COMMITTED,
            committed_at=self.now,
        )
        result = resolve_operational_readiness(occurrence, observed_at=self.now)
        self.assertEqual(result.status, ReadinessStatus.BLOCKED)
        self.assertTrue(any(check.reason_code == "capacity_overcommitted" for check in result.blocking_items))
