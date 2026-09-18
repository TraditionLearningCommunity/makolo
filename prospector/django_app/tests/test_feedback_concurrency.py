from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest import skipUnless

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_app.models import ProspectorFeedbackEvent
from prospector.django_feedback import DjangoFeedbackStore
from prospector.django_frontier import DjangoFrontierStore
from prospector.feedback import (
    FeedbackProducer,
    FeedbackSignal,
    ProspectingFeedback,
)


POSTGRESQL = connection.vendor == "postgresql"


@skipUnless(POSTGRESQL, "feedback concurrency contract requires PostgreSQL advisory locks")
class FeedbackConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        self.target = DjangoFrontierStore().admit_sync(
            ProspectingCandidate(
                locator="https://example.test/feedback",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        discovered_at=self.now,
                        provider="test",
                    ),
                ),
            )
        )

    def event(self):
        return ProspectingFeedback(
            event_key="resolver:concurrent:1",
            target_key=self.target.target_key,
            signal=FeedbackSignal.REALITY_NEW,
            producer=FeedbackProducer.RESOLVER,
            source_ref="resolution:concurrent:1",
            occurred_at=self.now,
        )

    def test_same_event_recorded_concurrently_creates_one_row(self):
        def record(_index):
            close_old_connections()
            try:
                return DjangoFeedbackStore().record_sync(self.event())
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(record, range(8)))

        self.assertEqual(sum(bool(value) for value in outcomes), 1)
        self.assertEqual(ProspectorFeedbackEvent.objects.count(), 1)
