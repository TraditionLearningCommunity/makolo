from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization

from .models import CapacityPool
from .services import InsufficientCapacity, reserve_capacity


User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Ce test exerce le verrouillage PostgreSQL réel.")
class CapacityConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.user = User.objects.create_user(username="capacity-concurrency", email="capacity-concurrency@example.com", password="Capacity-2026!")
        self.space = Organization.objects.create(name="Concurrent Capacity", created_by=self.user)
        self.activity = Activity.objects.create(space=self.space, created_by=self.user, title="Capacité concurrente")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=1),
        )
        self.pool = CapacityPool.objects.create(activity=self.activity, occurrence=self.occurrence, total_quantity=1)
        self.journey_ids = [
            create_journey(
                initiated_by=self.user,
                beneficiary=self.user,
                activity=self.activity,
                occurrence=self.occurrence,
                workflow=WorkflowKind.REGISTRATION,
            ).pk
            for _ in range(2)
        ]

    def _reserve(self, barrier, journey_id):
        close_old_connections()
        try:
            from journeys.models import Journey

            barrier.wait(timeout=5)
            journey = Journey.objects.get(pk=journey_id)
            pool = CapacityPool.objects.get(pk=self.pool.pk)
            try:
                reserve_capacity(pool=pool, journey=journey, quantity=1, source_key=f"race:{journey_id}")
                return "success"
            except InsufficientCapacity:
                return "insufficient_capacity"
        finally:
            connection.close()

    def test_two_simultaneous_holds_never_oversell_one_place(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._reserve, barrier, journey_id) for journey_id in self.journey_ids]
            results = [future.result(timeout=10) for future in futures]

        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("insufficient_capacity"), 1)
