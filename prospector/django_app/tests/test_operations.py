from datetime import datetime, timedelta, timezone

from django.test import TestCase

from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_app.models import (
    ProspectorBudgetCounter,
    ProspectorBudgetReservation,
    ProspectorFeedbackEvent,
    ProspectorFeedbackProjection,
    ProspectorFrontierEntry,
    ProspectorSourceCheckpoint,
)
from prospector.django_frontier import DjangoFrontierStore
from prospector.django_operations import (
    DjangoOperationsReader,
    DjangoProspectorMaintenance,
)
from prospector.feedback import FeedbackProducer, FeedbackSignal
from prospector.frontier import FrontierState


class DjangoOperationsTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
        self.frontier = DjangoFrontierStore()

    def admit(self, name):
        return self.frontier.admit_sync(
            ProspectingCandidate(
                locator=f"https://example.test/{name}",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        provider="test-index",
                        discovered_at=self.now - timedelta(minutes=10),
                    ),
                ),
            ),
            available_at=self.now - timedelta(minutes=5),
        )

    def test_snapshot_reports_aggregates_without_locator_data(self):
        target = self.admit("ready")
        stale = self.admit("stale")
        ProspectorFrontierEntry.objects.filter(
            target_key=stale.target_key
        ).update(
            status=FrontierState.CLAIMED.value,
            claimed_by="dead-worker",
            claimed_at=self.now - timedelta(minutes=5),
            lease_expires_at=self.now - timedelta(minutes=1),
            claim_token="11111111-1111-1111-1111-111111111111",
        )
        ProspectorFeedbackEvent.objects.create(
            event_key="ops-feedback-1",
            target_key=target.target_key,
            signal=FeedbackSignal.REALITY_NEW.value,
            producer=FeedbackProducer.RESOLVER.value,
            source_ref="resolver:1",
            occurred_at=self.now,
            scopes=[],
        )
        ProspectorFeedbackProjection.objects.create(
            policy_key="ops",
            policy_fingerprint="f" * 64,
            last_event_id=0,
        )
        ProspectorSourceCheckpoint.objects.create(
            source_name="source",
            mission_key="mission",
            mission_fingerprint="m" * 64,
            source_revision="r1",
            cursor={},
            exhausted=False,
            checkpoint_updated_at=self.now - timedelta(minutes=20),
        )

        snapshot = DjangoOperationsReader().snapshot_sync(now=self.now)
        payload = snapshot.to_dict()

        self.assertEqual(snapshot.frontier_total, 2)
        self.assertEqual(snapshot.ready_due, 1)
        self.assertEqual(snapshot.stale_claims, 1)
        self.assertGreaterEqual(snapshot.oldest_ready_age_seconds, 300)
        self.assertEqual(snapshot.feedback_projection_lag_events, 1)
        self.assertGreaterEqual(
            snapshot.oldest_active_checkpoint_age_seconds,
            1200,
        )
        rendered = str(payload)
        self.assertNotIn("https://example.test", rendered)
        self.assertNotIn(target.target_key, rendered)

    def test_prune_expired_budgets_is_dry_run_by_default_contract(self):
        expired_start = self.now - timedelta(hours=2)
        expired_end = self.now - timedelta(hours=1)
        ProspectorBudgetCounter.objects.create(
            policy_key="old",
            scope_kind="host",
            scope_key="example.test",
            period_start=expired_start,
            period_end=expired_end,
            used_count=1,
        )
        ProspectorBudgetReservation.objects.create(
            handoff_key="observation:v1:" + ("a" * 64),
            policy_key="old",
            period_start=expired_start,
            period_end=expired_end,
            scopes={"host": "example.test"},
            limits={"host": 2},
            reserved_at=expired_start,
        )
        maintenance = DjangoProspectorMaintenance()

        dry = maintenance.prune_expired_budgets_sync(
            before=self.now,
            apply=False,
        )
        self.assertEqual(dry["budget_counters"], 1)
        self.assertEqual(dry["budget_reservations"], 1)
        self.assertEqual(ProspectorBudgetCounter.objects.count(), 1)

        applied = maintenance.prune_expired_budgets_sync(
            before=self.now,
            apply=True,
        )
        self.assertTrue(applied["apply"])
        self.assertEqual(ProspectorBudgetCounter.objects.count(), 0)
        self.assertEqual(ProspectorBudgetReservation.objects.count(), 0)
