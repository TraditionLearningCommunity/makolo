from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from journeys.models import ExternalBeneficiary, Journey, JourneyStatus, WorkflowKind

from .models import OccurrenceCheckpoint, OccurrenceQueue, QueueEntry, QueueEntryStatus, QueueStatus
from .queue_selectors import queue_position, queue_snapshot
from .queue_services import (
    call_next,
    cancel_entry,
    close_queue,
    enter_queue,
    expire_entry,
    pause_queue,
    resume_queue,
    serve_entry,
)


User = get_user_model()


class O3LiveQueueTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.owner = User.objects.create_user(username="o3-owner", email="o3-owner@example.test", password="pw")
        self.manager = User.objects.create_user(username="o3-manager", email="o3-manager@example.test", password="pw")
        self.other_user = User.objects.create_user(username="o3-other", email="o3-other@example.test", password="pw")
        self.first = User.objects.create_user(username="o3-first", email="o3-first@example.test", password="pw")
        self.second = User.objects.create_user(username="o3-second", email="o3-second@example.test", password="pw")
        self.activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O3 Queue")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="O3 occurrence",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, hours=2),
        )
        grant_activity_role(
            profile=self.manager,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o3-test",
        )
        for profile in (self.first, self.second):
            Journey.objects.create(
                initiated_by=profile,
                beneficiary=profile,
                activity=self.activity,
                occurrence=self.occurrence,
                workflow=WorkflowKind.REGISTRATION,
                status=JourneyStatus.CONFIRMED,
            )
        self.external = ExternalBeneficiary.objects.create(
            display_name="O3 External",
            email="o3-external@example.test",
            created_by=self.owner,
        )
        Journey.objects.create(
            initiated_by=self.owner,
            external_beneficiary=self.external,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence,
            key="service",
            label="Service",
        )
        self.queue = OccurrenceQueue.objects.create(
            occurrence=self.occurrence,
            checkpoint=self.checkpoint,
            key="service",
            label="File service",
        )

    def test_queue_checkpoint_must_match_occurrence_and_key_is_scoped(self):
        other_activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="Other")
        other_occurrence = Occurrence.objects.create(
            activity=other_activity,
            label="Other",
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=1),
        )
        with self.assertRaises(ValidationError):
            OccurrenceQueue.objects.create(
                occurrence=other_occurrence,
                checkpoint=self.checkpoint,
                key="bad",
                label="Bad",
            )
        with self.assertRaises(Exception):
            OccurrenceQueue.objects.create(occurrence=self.occurrence, key="service", label="Duplicate")
        OccurrenceQueue.objects.create(occurrence=other_occurrence, key="service", label="Allowed")

    def test_entry_requires_profile_xor_external_beneficiary(self):
        with self.assertRaises(ValidationError):
            QueueEntry(
                queue=self.queue,
                sequence=1,
                entered_by=self.manager,
            ).full_clean()
        with self.assertRaises(ValidationError):
            QueueEntry(
                queue=self.queue,
                profile=self.first,
                external_beneficiary=self.external,
                sequence=1,
                entered_by=self.manager,
            ).full_clean()

    def test_queue_lifecycle_is_simple_and_closed_is_terminal(self):
        paused = pause_queue(actor=self.manager, queue=self.queue)
        self.assertEqual(paused.status, QueueStatus.PAUSED)
        reopened = resume_queue(actor=self.manager, queue=paused)
        self.assertEqual(reopened.status, QueueStatus.OPEN)
        closed = close_queue(actor=self.manager, queue=reopened)
        self.assertEqual(closed.status, QueueStatus.CLOSED)
        with self.assertRaises(ValidationError):
            resume_queue(actor=self.manager, queue=closed)

    def test_fifo_enter_call_and_serve_are_deterministic(self):
        first = enter_queue(actor=self.manager, queue=self.queue, profile=self.first, client_reference="first")
        second = enter_queue(actor=self.manager, queue=self.queue, profile=self.second, client_reference="second")
        self.assertEqual((first.sequence, second.sequence), (1, 2))
        self.assertEqual(queue_position(entry=first), 1)
        self.assertEqual(queue_position(entry=second), 2)
        called = call_next(actor=self.manager, queue=self.queue)
        self.assertEqual(called.pk, first.pk)
        served = serve_entry(actor=self.manager, entry=called)
        self.assertEqual(served.status, QueueEntryStatus.SERVED)
        next_called = call_next(actor=self.manager, queue=self.queue)
        self.assertEqual(next_called.pk, second.pk)

    def test_external_beneficiary_and_idempotent_retry(self):
        entry = enter_queue(
            actor=self.manager,
            queue=self.queue,
            external_beneficiary=self.external,
            source="operator",
            client_reference="external-retry",
        )
        retry = enter_queue(
            actor=self.manager,
            queue=self.queue,
            external_beneficiary=self.external,
            source="operator",
            client_reference="external-retry",
        )
        self.assertEqual(entry.pk, retry.pk)
        self.assertEqual(QueueEntry.objects.filter(queue=self.queue, external_beneficiary=self.external).count(), 1)

    def test_active_subject_is_not_duplicated_but_can_reenter_after_terminal_state(self):
        first = enter_queue(actor=self.manager, queue=self.queue, profile=self.first)
        duplicate = enter_queue(actor=self.manager, queue=self.queue, profile=self.first)
        self.assertEqual(first.pk, duplicate.pk)
        cancel_entry(actor=self.manager, entry=first)
        second = enter_queue(actor=self.manager, queue=self.queue, profile=self.first)
        self.assertNotEqual(first.pk, second.pk)
        self.assertGreater(second.sequence, first.sequence)

    def test_paused_or_closed_queue_rejects_enter_and_call(self):
        self.queue.status = QueueStatus.PAUSED
        self.queue.save(update_fields=["status", "updated_at"])
        with self.assertRaises(ValidationError):
            enter_queue(actor=self.manager, queue=self.queue, profile=self.first)
        with self.assertRaises(ValidationError):
            call_next(actor=self.manager, queue=self.queue)

    def test_authority_is_server_side(self):
        with self.assertRaises(PermissionDenied):
            enter_queue(actor=self.other_user, queue=self.queue, profile=self.first)
        entry = enter_queue(actor=self.manager, queue=self.queue, profile=self.first)
        with self.assertRaises(PermissionDenied):
            call_next(actor=self.other_user, queue=self.queue)
        self.assertEqual(entry.status, QueueEntryStatus.WAITING)

    def test_invalid_transitions_are_rejected(self):
        entry = enter_queue(actor=self.manager, queue=self.queue, profile=self.first)
        with self.assertRaises(ValidationError):
            serve_entry(actor=self.manager, entry=entry)
        expired = expire_entry(actor=self.manager, entry=entry)
        self.assertEqual(expired.status, QueueEntryStatus.EXPIRED)
        with self.assertRaises(ValidationError):
            cancel_entry(actor=self.manager, entry=expired)

    def test_self_entry_and_cancel_only_apply_to_actor(self):
        entry = enter_queue(actor=self.first, queue=self.queue, profile=self.first, allow_self=True)
        self.assertEqual(entry.profile, self.first)
        with self.assertRaises(PermissionDenied):
            cancel_entry(actor=self.second, entry=entry, allow_self=True)
        cancelled = cancel_entry(actor=self.first, entry=entry, allow_self=True)
        self.assertEqual(cancelled.status, QueueEntryStatus.CANCELLED)

    def test_queue_events_are_minimal_and_metrics_are_derived(self):
        entry = enter_queue(actor=self.manager, queue=self.queue, profile=self.first)
        called = call_next(actor=self.manager, queue=self.queue)
        served = serve_entry(actor=self.manager, entry=called)
        event_types = set(
            DomainEventOutbox.objects.filter(source_id=str(entry.pk)).values_list("event_type", flat=True)
        )
        self.assertTrue({DomainEventType.QUEUE_ENTERED, DomainEventType.QUEUE_CALLED, DomainEventType.QUEUE_SERVED}.issubset(event_types))
        event = DomainEventOutbox.objects.get(source_id=str(entry.pk), event_type=DomainEventType.QUEUE_SERVED)
        serialized = str(event.payload)
        self.assertNotIn(self.first.email, serialized)
        self.assertNotIn("credential", serialized.lower())
        snapshot = queue_snapshot(queue=self.queue, now=served.served_at)
        self.assertEqual(snapshot["served"], 1)
        self.assertEqual(snapshot["served_last_hour"], 1)
        self.assertIsNotNone(snapshot["average_wait_seconds"])
