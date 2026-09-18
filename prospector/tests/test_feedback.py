from datetime import datetime, timezone
from unittest import TestCase

from prospector.contracts import ProspectingEvidence, ProspectingTarget
from prospector.feedback import (
    AdaptivePolicy,
    CandidateLearning,
    FeedbackPolicy,
    FeedbackProducer,
    FeedbackSignal,
    LearningScope,
    LearningStat,
    ProspectingFeedback,
    feedback_scopes_for_target,
    score_target,
)


def feedback_policy(**overrides):
    weights = {
        FeedbackSignal.OBSERVATION_VALID: 1,
        FeedbackSignal.STRUCTURED_INFORMATION: 3,
        FeedbackSignal.REALITY_NEW: 8,
        FeedbackSignal.REALITY_REFRESHED: 5,
        FeedbackSignal.NO_USEFUL_INFORMATION: -2,
        FeedbackSignal.DOWNSTREAM_REJECTED: -5,
    }
    weights.update(overrides)
    return FeedbackPolicy(policy_key="test-v1", weights=weights)


class FeedbackContractsTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)

    def target(self):
        return ProspectingTarget(
            target_key="web_url:v1:" + ("a" * 64),
            locator="https://example.test/resource",
            kind="web_url",
            first_discovered_at=self.now,
            evidence=(
                ProspectingEvidence(
                    method="external_index",
                    discovered_at=self.now,
                    provider="common-crawl",
                ),
                ProspectingEvidence(
                    method="web_graph",
                    discovered_at=self.now,
                    source_target_key="web_url:v1:" + ("b" * 64),
                ),
            ),
            policy_context={
                "mission_key": "rdc",
                "campaign_key": "skills",
                "branch_key": "root-a",
            },
        )

    def adaptive(self):
        return AdaptivePolicy(
            feedback=feedback_policy(),
            dimension_weights={
                "lineage_target": 4,
                "method": 2,
                "provider": 1,
                "mission": 1,
                "campaign": 1,
                "branch": 1,
            },
            min_samples_for_exploitation=3,
            exploration_numerator=1,
            exploration_denominator=4,
            candidate_pool_multiplier=4,
            projection_batch_size=50,
        )

    def test_feedback_event_has_no_business_payload(self):
        event = ProspectingFeedback(
            event_key="resolver:42",
            target_key=self.target().target_key,
            signal=FeedbackSignal.REALITY_NEW,
            producer=FeedbackProducer.RESOLVER,
            source_ref="resolution:42",
            occurred_at=self.now,
        )
        self.assertFalse(hasattr(event, "activity"))
        self.assertFalse(hasattr(event, "requirement"))
        self.assertFalse(hasattr(event, "facts"))
        self.assertFalse(hasattr(event, "metadata"))

    def test_policy_requires_explicit_weight_for_every_signal(self):
        weights = {
            FeedbackSignal.OBSERVATION_VALID: 1,
        }
        with self.assertRaises(ValueError):
            FeedbackPolicy(policy_key="broken", weights=weights)

    def test_policy_fingerprint_changes_when_weights_change(self):
        first = feedback_policy()
        second = feedback_policy(**{FeedbackSignal.REALITY_NEW: 9})
        self.assertNotEqual(first.fingerprint, second.fingerprint)

    def test_scopes_include_lineage_and_operational_dimensions_only(self):
        scopes = set(feedback_scopes_for_target(self.target()))
        self.assertIn(
            LearningScope("lineage_target", self.target().target_key),
            scopes,
        )
        self.assertIn(
            LearningScope(
                "lineage_target",
                "web_url:v1:" + ("b" * 64),
            ),
            scopes,
        )
        self.assertIn(LearningScope("method", "external_index"), scopes)
        self.assertIn(LearningScope("method", "web_graph"), scopes)
        self.assertIn(LearningScope("provider", "common-crawl"), scopes)
        self.assertIn(LearningScope("mission", "rdc"), scopes)
        self.assertIn(LearningScope("campaign", "skills"), scopes)
        self.assertIn(LearningScope("branch", "root-a"), scopes)

    def test_score_is_weighted_without_float_or_hidden_prior(self):
        policy = self.adaptive()
        target = self.target()
        scopes = feedback_scopes_for_target(target)
        stats = {
            scope: LearningStat(scope, sample_count=4, score_sum=20)
            for scope in scopes
        }
        learned = score_target(target, stats=stats, policy=policy)
        self.assertEqual(learned.support_samples, 4)
        self.assertEqual(learned.mean_score, 5)

        empty = score_target(target, stats={}, policy=policy)
        self.assertEqual(empty, CandidateLearning(0, 0, 0))
        self.assertEqual(empty.mean_score, 0)

    def test_exploration_slots_are_explicit_and_ceil_small_batches(self):
        policy = self.adaptive()
        self.assertEqual(policy.exploration_slots(1), 1)
        self.assertEqual(policy.exploration_slots(4), 1)
        self.assertEqual(policy.exploration_slots(5), 2)
