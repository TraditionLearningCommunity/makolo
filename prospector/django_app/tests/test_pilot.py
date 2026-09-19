from datetime import datetime, timezone

from django.test import TestCase

from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_feedback import DjangoFeedbackStore
from prospector.django_frontier import DjangoFrontierStore
from prospector.django_pilot import DjangoPilotSnapshotReader
from prospector.feedback import (
    FeedbackProducer,
    FeedbackSignal,
    ProspectingFeedback,
)


class DjangoPilotSnapshotTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 19, tzinfo=timezone.utc)
        self.frontier = DjangoFrontierStore()
        self.fingerprint = "f" * 64

    def admit(self, suffix, *, method="external_index", provider="common_crawl"):
        return self.frontier.admit_sync(
            ProspectingCandidate(
                locator=f"https://example.test/{suffix}",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method=method,
                        provider=provider,
                        discovered_at=self.now,
                    ),
                ),
                policy_context={
                    "mission_key": "pilot",
                    "mission_fingerprint": self.fingerprint,
                },
            )
        )

    def test_snapshot_is_scoped_and_contains_only_aggregate_counts(self):
        target = self.admit("a")
        self.admit("b", method="web_graph", provider=None)
        self.frontier.admit_sync(
            ProspectingCandidate(
                locator="https://other.test/outside",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        provider="other",
                        discovered_at=self.now,
                    ),
                ),
                policy_context={
                    "mission_key": "other",
                    "mission_fingerprint": "x" * 64,
                },
            )
        )
        DjangoFeedbackStore().record_sync(
            ProspectingFeedback(
                event_key="pilot-feedback-1",
                target_key=target.target_key,
                signal=FeedbackSignal.REALITY_NEW,
                producer=FeedbackProducer.RESOLVER,
                source_ref="resolver:1",
                occurred_at=self.now,
            )
        )

        # A later admission from another mission overwrites the entry's current
        # policy_context, but must not erase PX8 mission attribution from its
        # durable evidence.
        self.frontier.admit_sync(
            ProspectingCandidate(
                locator="https://example.test/a",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        provider="other-index",
                        discovered_at=self.now,
                    ),
                ),
                policy_context={
                    "mission_key": "later-other",
                    "mission_fingerprint": "y" * 64,
                },
            )
        )

        # Feedback emitted after another mission becomes the target's current
        # context must not be attributed back to the PX8 mission merely because
        # the target_key is shared.
        self.frontier.admit_sync(
            ProspectingCandidate(
                locator="https://example.test/a",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        provider="other-index-2",
                        discovered_at=self.now,
                    ),
                ),
                policy_context={
                    "mission_key": "later-other",
                    "mission_fingerprint": "z" * 64,
                },
            )
        )
        DjangoFeedbackStore().record_sync(
            ProspectingFeedback(
                event_key="other-feedback-1",
                target_key=target.target_key,
                signal=FeedbackSignal.DOWNSTREAM_REJECTED,
                producer=FeedbackProducer.RESOLVER,
                source_ref="resolver:other",
                occurred_at=self.now,
            )
        )

        # Same fingerprint but another mission_key must remain isolated.
        self.frontier.admit_sync(
            ProspectingCandidate(
                locator="https://same-fingerprint.test/other-mission",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        provider="other",
                        discovered_at=self.now,
                    ),
                ),
                policy_context={
                    "mission_key": "other-mission",
                    "mission_fingerprint": self.fingerprint,
                },
            )
        )

        snapshot = DjangoPilotSnapshotReader().snapshot_sync(
            mission_key="pilot",
            mission_fingerprint=self.fingerprint,
        )

        self.assertEqual(snapshot.entry_count, 2)
        self.assertEqual(snapshot.evidence_count, 2)
        self.assertEqual(snapshot.feedback_events, 1)
        self.assertEqual(snapshot.feedback_signals["reality_new"], 1)
        self.assertEqual(snapshot.evidence_methods["external_index"], 1)
        self.assertEqual(snapshot.evidence_methods["web_graph"], 1)
        self.assertEqual(snapshot.providers["common_crawl"], 1)
