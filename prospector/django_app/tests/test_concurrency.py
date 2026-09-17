from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone as dt_timezone
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_frontier import DjangoFrontierStore
from prospector.django_app.models import ProspectorFrontierEntry


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
            close_old_connections()

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
        self.assertEqual(entry.discovery_count, 16)

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
