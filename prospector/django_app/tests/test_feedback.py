from datetime import datetime, timezone

from django.test import TestCase

from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_app.models import (
    ProspectorFeedbackEvent,
    ProspectorFeedbackProjection,
    ProspectorFeedbackStat,
)
from prospector.django_feedback import DjangoFeedbackStore
from prospector.django_frontier import DjangoFrontierStore
from prospector.errors import FrontierConflictError
from prospector.feedback import (
    FeedbackPolicy,
    FeedbackProducer,
    FeedbackSignal,
    LearningScope,
    ProspectingFeedback,
)


def make_policy(*, new_weight=8):
    return FeedbackPolicy(
        policy_key="learning-v1",
        weights={
            FeedbackSignal.OBSERVATION_VALID: 1,
            FeedbackSignal.STRUCTURED_INFORMATION: 3,
            FeedbackSignal.REALITY_NEW: new_weight,
            FeedbackSignal.REALITY_REFRESHED: 5,
            FeedbackSignal.NO_USEFUL_INFORMATION: -2,
            FeedbackSignal.DOWNSTREAM_REJECTED: -5,
        },
    )


class DjangoFeedbackStoreTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        self.frontier = DjangoFrontierStore()
        self.feedback = DjangoFeedbackStore()
        self.target = self.frontier.admit_sync(
            ProspectingCandidate(
                locator="https://example.test/resource",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        discovered_at=self.now,
                        provider="test-index",
                    ),
                ),
                policy_context={
                    "mission_key": "rdc",
                    "campaign_key": "skills",
                    "branch_key": "root",
                },
            )
        )

    def event(self, *, key="resolver:1", signal=FeedbackSignal.REALITY_NEW):
        return ProspectingFeedback(
            event_key=key,
            target_key=self.target.target_key,
            signal=signal,
            producer=FeedbackProducer.RESOLVER,
            source_ref=key,
            occurred_at=self.now,
        )

    def test_record_is_idempotent_and_scopes_are_snapshotted(self):
        self.assertTrue(self.feedback.record_sync(self.event()))
        self.assertFalse(self.feedback.record_sync(self.event()))

        self.assertEqual(ProspectorFeedbackEvent.objects.count(), 1)
        row = ProspectorFeedbackEvent.objects.get()
        scopes = {(item["kind"], item["key"]) for item in row.scopes}
        self.assertIn(("lineage_target", self.target.target_key), scopes)
        self.assertIn(("method", "external_index"), scopes)
        self.assertIn(("provider", "test-index"), scopes)
        self.assertIn(("mission", "rdc"), scopes)
        self.assertIn(("campaign", "skills"), scopes)
        self.assertIn(("branch", "root"), scopes)

    def test_event_key_collision_with_different_payload_is_rejected(self):
        self.feedback.record_sync(self.event())
        with self.assertRaises(FrontierConflictError):
            self.feedback.record_sync(
                self.event(signal=FeedbackSignal.DOWNSTREAM_REJECTED)
            )

    def test_projection_counts_signs_and_advances_checkpoint(self):
        self.feedback.record_sync(self.event(key="a"))
        self.feedback.record_sync(
            self.event(
                key="b",
                signal=FeedbackSignal.DOWNSTREAM_REJECTED,
            )
        )
        policy = make_policy()

        processed = self.feedback.refresh_all_sync(policy, batch_size=1)

        self.assertEqual(processed, 2)
        projection = ProspectorFeedbackProjection.objects.get(
            policy_fingerprint=policy.fingerprint
        )
        self.assertEqual(
            projection.last_event_id,
            ProspectorFeedbackEvent.objects.order_by("-id").values_list(
                "id",
                flat=True,
            ).first(),
        )

        stat = ProspectorFeedbackStat.objects.get(
            policy_fingerprint=policy.fingerprint,
            scope_kind="lineage_target",
            scope_key=self.target.target_key,
        )
        self.assertEqual(stat.sample_count, 2)
        self.assertEqual(stat.score_sum, 3)
        self.assertEqual(stat.positive_count, 1)
        self.assertEqual(stat.negative_count, 1)
        self.assertEqual(stat.neutral_count, 0)

    def test_policy_change_rebuilds_independent_projection_from_raw_events(self):
        self.feedback.record_sync(self.event())
        first = make_policy(new_weight=8)
        second = make_policy(new_weight=2)

        self.feedback.refresh_all_sync(first, batch_size=10)
        self.feedback.refresh_all_sync(second, batch_size=10)

        first_stat = ProspectorFeedbackStat.objects.get(
            policy_fingerprint=first.fingerprint,
            scope_kind="lineage_target",
            scope_key=self.target.target_key,
        )
        second_stat = ProspectorFeedbackStat.objects.get(
            policy_fingerprint=second.fingerprint,
            scope_kind="lineage_target",
            scope_key=self.target.target_key,
        )
        self.assertEqual(first_stat.score_sum, 8)
        self.assertEqual(second_stat.score_sum, 2)
        self.assertEqual(ProspectorFeedbackEvent.objects.count(), 1)
        self.assertEqual(ProspectorFeedbackProjection.objects.count(), 2)

    def test_zero_weight_is_neutral_not_missing(self):
        policy = FeedbackPolicy(
            policy_key="neutral-v1",
            weights={
                FeedbackSignal.OBSERVATION_VALID: 0,
                FeedbackSignal.STRUCTURED_INFORMATION: 1,
                FeedbackSignal.REALITY_NEW: 2,
                FeedbackSignal.REALITY_REFRESHED: 1,
                FeedbackSignal.NO_USEFUL_INFORMATION: -1,
                FeedbackSignal.DOWNSTREAM_REJECTED: -2,
            },
        )
        self.feedback.record_sync(
            ProspectingFeedback(
                event_key="observer:neutral",
                target_key=self.target.target_key,
                signal=FeedbackSignal.OBSERVATION_VALID,
                producer=FeedbackProducer.OBSERVER,
                source_ref="observation:1",
                occurred_at=self.now,
            )
        )
        self.feedback.refresh_all_sync(policy, batch_size=10)
        stat = ProspectorFeedbackStat.objects.get(
            policy_fingerprint=policy.fingerprint,
            scope_kind="lineage_target",
            scope_key=self.target.target_key,
        )
        self.assertEqual(stat.sample_count, 1)
        self.assertEqual(stat.score_sum, 0)
        self.assertEqual(stat.neutral_count, 1)


    def test_projection_rebuild_recovers_same_derived_stats_from_raw_events(self):
        self.feedback.record_sync(self.event(key="rebuild-a"))
        self.feedback.record_sync(
            self.event(
                key="rebuild-b",
                signal=FeedbackSignal.DOWNSTREAM_REJECTED,
            )
        )
        policy = make_policy()
        self.feedback.refresh_all_sync(policy, batch_size=10)
        before = ProspectorFeedbackStat.objects.get(
            policy_fingerprint=policy.fingerprint,
            scope_kind="lineage_target",
            scope_key=self.target.target_key,
        )
        expected = (
            before.sample_count,
            before.score_sum,
            before.positive_count,
            before.negative_count,
        )

        dry = self.feedback.rebuild_projection_sync(
            policy,
            batch_size=1,
            apply=False,
        )
        self.assertFalse(dry["apply"])
        self.assertEqual(ProspectorFeedbackEvent.objects.count(), 2)

        rebuilt = self.feedback.rebuild_projection_sync(
            policy,
            batch_size=1,
            apply=True,
        )
        self.assertEqual(rebuilt["processed"], 2)
        after = ProspectorFeedbackStat.objects.get(
            policy_fingerprint=policy.fingerprint,
            scope_kind="lineage_target",
            scope_key=self.target.target_key,
        )
        actual = (
            after.sample_count,
            after.score_sum,
            after.positive_count,
            after.negative_count,
        )
        self.assertEqual(actual, expected)
        self.assertEqual(ProspectorFeedbackEvent.objects.count(), 2)
