from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .models import OccurrenceQueue, QueueEntry
from .queue_services import enter_queue


User = get_user_model()


class O3QueueConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.owner = User.objects.create_user(username="o3-concurrency-owner", email="o3-owner@example.test", password="pw")
        self.manager = User.objects.create_user(username="o3-concurrency-manager", email="o3-manager@example.test", password="pw")
        self.first = User.objects.create_user(username="o3-concurrency-first", email="o3-first@example.test", password="pw")
        self.second = User.objects.create_user(username="o3-concurrency-second", email="o3-second@example.test", password="pw")
        self.activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O3 concurrency")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="O3 concurrency occurrence",
            start_at=timezone.now() + timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=3),
        )
        grant_activity_role(
            profile=self.manager,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o3-concurrency-test",
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
        self.queue = OccurrenceQueue.objects.create(occurrence=self.occurrence, key="live", label="Live")

    def _enter(self, barrier, profile_id, reference):
        close_old_connections()
        try:
            actor = User.objects.get(pk=self.manager.pk)
            profile = User.objects.get(pk=profile_id)
            queue = OccurrenceQueue.objects.get(pk=self.queue.pk)
            barrier.wait(timeout=5)
            entry = enter_queue(
                actor=actor,
                queue=queue,
                profile=profile,
                source="o3-concurrency",
                client_reference=reference,
            )
            return entry.sequence
        finally:
            connection.close()

    def test_entries_receive_distinct_monotonic_sequences_under_backend_contract(self):
        if connection.vendor == "postgresql":
            barrier = Barrier(2)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(self._enter, barrier, self.first.pk, "first"),
                    pool.submit(self._enter, barrier, self.second.pk, "second"),
                ]
                sequences = sorted(future.result(timeout=10) for future in futures)
        else:
            first = enter_queue(
                actor=self.manager,
                queue=self.queue,
                profile=self.first,
                source="o3-backend-contract",
                client_reference="first",
            )
            second = enter_queue(
                actor=self.manager,
                queue=self.queue,
                profile=self.second,
                source="o3-backend-contract",
                client_reference="second",
            )
            sequences = [first.sequence, second.sequence]

        self.assertEqual(sequences, [1, 2])
        self.assertEqual(
            list(
                QueueEntry.objects.filter(queue=self.queue)
                .order_by("sequence")
                .values_list("sequence", flat=True)
            ),
            [1, 2],
        )
        self.queue.refresh_from_db()
        self.assertEqual(self.queue.next_sequence, 3)
