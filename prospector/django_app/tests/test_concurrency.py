from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone as dt_timezone
from unittest import skipUnless

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_budget import DjangoBudgetStore
from prospector.django_frontier import DjangoFrontierStore
from prospector.django_app.models import (
    ProspectorBudgetCounter,
    ProspectorBudgetReservation,
    ProspectorFrontierEntry,
    ProspectorFrontierEvidence,
)


POSTGRESQL = connection.vendor == "postgresql"


@skipUnless(POSTGRESQL, "PX1 concurrency contracts require PostgreSQL row locks")
class PostgreSQLFrontierConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.now = datetime(2026, 9, 18, 9, 0, tzinfo=dt_timezone.utc)

    def candidate(self, index=0):
        return ProspectingCandidate(
            locator=f"https://example.test/resource/{index}",
            kind="web_url",
            evidence=(
                ProspectingEvidence(
                    method="external_index",
                    discovered_at=self.now,
                    provider="test-index",
                    attributes={"source": "concurrency"},
                ),
            ),
        )

    @staticmethod
    def _in_thread(callback):
        close_old_connections()
        try:
            return callback()
        finally:
            # Thread-local DB connections outlive the callback when executor
            # threads stay alive. Close them explicitly so Django can destroy
            # the PostgreSQL test database deterministically.
            connections.close_all()

    def test_concurrent_admission_creates_one_target_and_counts_every_admission(self):
        candidate = self.candidate(1)

        def admit():
            return self._in_thread(
                lambda: DjangoFrontierStore().admit_sync(candidate).target_key
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            keys = list(executor.map(lambda _: admit(), range(16)))

        self.assertEqual(len(set(keys)), 1)
        entry = ProspectorFrontierEntry.objects.get()
        evidence = ProspectorFrontierEvidence.objects.get()
        self.assertEqual(entry.discovery_count, 16)
        self.assertEqual(evidence.discovery_count, 16)

    def test_concurrent_claimers_receive_disjoint_targets(self):
        store = DjangoFrontierStore()
        for index in range(12):
            store.admit_sync(self.candidate(index))

        def claim(worker_id):
            return self._in_thread(
                lambda: {
                    item.target.target_key
                    for item in DjangoFrontierStore().claim_sync(
                        worker_id=worker_id,
                        limit=6,
                        lease_seconds=120,
                        now=self.now,
                    )
                }
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(claim, "worker-a")
            second_future = executor.submit(claim, "worker-b")
            first = first_future.result()
            second = second_future.result()

        self.assertEqual(len(first), 6)
        self.assertEqual(len(second), 6)
        self.assertTrue(first.isdisjoint(second))
        self.assertEqual(len(first | second), 12)



@skipUnless(POSTGRESQL, "PX4 budget concurrency contracts require PostgreSQL advisory locks")
class PostgreSQLBudgetConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.now = datetime(2026, 9, 18, 9, 0, tzinfo=dt_timezone.utc)
        self.period_end = datetime(2026, 9, 18, 10, 0, tzinfo=dt_timezone.utc)

    @staticmethod
    def _in_thread(callback):
        close_old_connections()
        try:
            return callback()
        finally:
            connections.close_all()

    def test_concurrent_unique_handoffs_never_exceed_host_limit(self):
        def reserve(index):
            return self._in_thread(
                lambda: DjangoBudgetStore().reserve_sync(
                    handoff_key=f"observation:v1:{index:064x}",
                    policy_key="px4-test-v1",
                    scopes={"host": "example.test"},
                    limits={"host": 5},
                    period_start=self.now,
                    period_end=self.period_end,
                    now=self.now,
                ).allowed
            )

        with ThreadPoolExecutor(max_workers=10) as executor:
            decisions = list(executor.map(reserve, range(12)))

        self.assertEqual(sum(decisions), 5)
        counter = ProspectorBudgetCounter.objects.get(
            policy_key="px4-test-v1",
            scope_kind="host",
            scope_key="example.test",
        )
        self.assertEqual(counter.used_count, 5)
        self.assertEqual(ProspectorBudgetReservation.objects.count(), 5)
