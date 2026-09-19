from datetime import datetime, timezone
from unittest import TestCase

from prospector.contracts import ProspectingEvidence, ProspectingTarget
from prospector.feedback import (
    AdaptivePolicy,
    FeedbackPolicy,
    FeedbackSignal,
    LearningScope,
    LearningStat,
    feedback_scopes_for_target,
    score_target,
)


class FeedbackLineageTests(TestCase):
    def test_child_inherits_parent_lineage_performance(self):
        now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        parent_key = "web_url:v1:" + ("b" * 64)
        child = ProspectingTarget(
            target_key="web_url:v1:" + ("a" * 64),
            locator="https://example.test/child",
            kind="web_url",
            first_discovered_at=now,
            evidence=(
                ProspectingEvidence(
                    method="web_graph",
                    discovered_at=now,
                    source_target_key=parent_key,
                    source_observation_ref="obs:parent:1",
                ),
            ),
        )
        feedback = FeedbackPolicy(
            policy_key="lineage-v1",
            weights={
                FeedbackSignal.OBSERVATION_VALID: 1,
                FeedbackSignal.STRUCTURED_INFORMATION: 3,
                FeedbackSignal.REALITY_NEW: 8,
                FeedbackSignal.REALITY_REFRESHED: 5,
                FeedbackSignal.NO_USEFUL_INFORMATION: -2,
                FeedbackSignal.DOWNSTREAM_REJECTED: -5,
            },
        )
        policy = AdaptivePolicy(
            feedback=feedback,
            dimension_weights={"lineage_target": 1},
            min_samples_for_exploitation=2,
            exploration_numerator=1,
            exploration_denominator=4,
            candidate_pool_multiplier=4,
            projection_batch_size=50,
        )
        parent_scope = LearningScope("lineage_target", parent_key)
        learned = score_target(
            child,
            stats={
                parent_scope: LearningStat(
                    scope=parent_scope,
                    sample_count=4,
                    score_sum=20,
                )
            },
            policy=policy,
        )
        self.assertIn(parent_scope, feedback_scopes_for_target(child))
        self.assertEqual(learned.support_samples, 4)
        self.assertEqual(learned.mean_score, 5)
