from datetime import datetime, timezone
from unittest import TestCase

from prospector.operations import (
    OperationsSnapshot,
    OperationsThresholds,
    evaluate_operations_health,
)


class OperationsHealthTests(TestCase):
    def snapshot(self, **overrides):
        values = {
            "captured_at": datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc),
            "frontier_total": 10,
            "ready_due": 2,
            "claimed": 1,
            "stale_claims": 0,
            "completed": 5,
            "suppressed": 2,
            "evidence_rows": 12,
            "source_checkpoints": 2,
            "active_source_checkpoints": 1,
            "feedback_events": 4,
            "feedback_projections": 1,
            "feedback_projection_lag_events": 0,
            "expired_budget_counters": 0,
            "expired_budget_reservations": 0,
            "oldest_ready_age_seconds": 20,
            "oldest_active_checkpoint_age_seconds": 30,
            "suppression_reasons": {"policy.host_denied": 2},
        }
        values.update(overrides)
        return OperationsSnapshot(**values)

    def test_health_is_ok_when_explicit_thresholds_are_met(self):
        health = evaluate_operations_health(
            self.snapshot(),
            OperationsThresholds(
                max_stale_claims=0,
                max_ready_age_seconds=20,
                max_feedback_projection_lag_events=0,
                max_active_checkpoint_age_seconds=30,
            ),
        )
        self.assertEqual(health.status, "ok")
        self.assertEqual(health.failed_checks, ())

    def test_health_reports_each_exceeded_threshold(self):
        health = evaluate_operations_health(
            self.snapshot(
                stale_claims=2,
                oldest_ready_age_seconds=100,
                feedback_projection_lag_events=7,
                oldest_active_checkpoint_age_seconds=200,
            ),
            OperationsThresholds(
                max_stale_claims=1,
                max_ready_age_seconds=50,
                max_feedback_projection_lag_events=5,
                max_active_checkpoint_age_seconds=100,
            ),
        )
        self.assertEqual(health.status, "degraded")
        self.assertEqual(
            set(health.failed_checks),
            {
                "stale_claims",
                "oldest_ready_age",
                "feedback_projection_lag",
                "active_checkpoint_age",
            },
        )

    def test_unconfigured_thresholds_do_not_create_hidden_policy(self):
        health = evaluate_operations_health(
            self.snapshot(stale_claims=999),
            OperationsThresholds(),
        )
        self.assertEqual(health.status, "ok")
