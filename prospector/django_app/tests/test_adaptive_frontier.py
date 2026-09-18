from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest import skipUnless

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from prospector.adaptive_frontier import DjangoAdaptiveFrontierStore
from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_app.models import ProspectorFrontierEntry
from prospector.django_feedback import DjangoFeedbackStore
from prospector.feedback import (
    AdaptivePolicy,
    FeedbackPolicy,
    FeedbackProducer,
    FeedbackSignal,
    ProspectingFeedback,
)
from prospector.frontier import FrontierState


POSTGRESQL = connection.vendor == "postgresql"


def feedback_policy():
    return FeedbackPolicy(
        policy_key="adaptive-v1",
        weights={
            FeedbackSignal.OBSERVATION_VALID: 1,
            FeedbackSignal.STRUCTURED_INFORMATION: 3,
            FeedbackSignal.REALITY_NEW: 8,
            FeedbackSignal.REALITY_REFRESHED: 5,
            FeedbackSignal.NO_USEFUL_INFORMATION: -2,
            FeedbackSignal.DOWNSTREAM_REJECTED: -5,
        },
    )


def adaptive_policy(*, exploration_numerator=1, exploration_denominator=2):
    return AdaptivePolicy(
        feedback=feedback_policy(),
        dimension_weights={"lineage_target": 1},
        min_samples_for_exploitation=3,
        exploration_numerator=exploration_numerator,
        exploration_denominator=exploration_denominator,
        candidate_pool_multiplier=4,
        projection_batch_size=2,
    )


class AdaptiveFrontierTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        self.base = DjangoFeedbackStore()
        self.store = DjangoAdaptiveFrontierStore(
            feedback_store=self.base,
            policy=adaptive_policy(),
        )

    def admit(self, name):
        return self.store.admit_sync(
            ProspectingCandidate(
                locator=f"https://example.test/{name}",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        discovered_at=self.now,
                        provider="test",
                    ),
                ),
            ),
            available_at=self.now,
        )

    def feedback(self, target, *, prefix, signal, count=3):
        for index in range(count):
            self.base.record_sync(
                ProspectingFeedback(
                    event_key=f"{prefix}:{index}",
                    target_key=target.target_key,
                    signal=signal,
                    producer=FeedbackProducer.RESOLVER,
                    source_ref=f"{prefix}:ref:{index}",
                    occurred_at=self.now,
                )
            )

    def test_claim_reserves_exploration_and_uses_yield_for_exploitation(self):
        high = self.admit("high")
        low = self.admit("low")
        novel = self.admit("novel")
        self.feedback(
            high,
            prefix="high",
            signal=FeedbackSignal.REALITY_NEW,
        )
        self.feedback(
            low,
            prefix="low",
            signal=FeedbackSignal.DOWNSTREAM_REJECTED,
        )

        claims = self.store.claim_sync(
            worker_id="adaptive-worker",
            limit=2,
            lease_seconds=60,
            now=self.now,
        )

        keys = {claim.target.target_key for claim in claims}
        self.assertEqual(keys, {high.target_key, novel.target_key})
        self.assertNotIn(low.target_key, keys)

    def test_zero_exploration_uses_best_learned_routes_only(self):
        high = self.admit("high")
        medium = self.admit("medium")
        low = self.admit("low")
        self.feedback(high, prefix="h", signal=FeedbackSignal.REALITY_NEW)
        self.feedback(
            medium,
            prefix="m",
            signal=FeedbackSignal.REALITY_REFRESHED,
        )
        self.feedback(
            low,
            prefix="l",
            signal=FeedbackSignal.DOWNSTREAM_REJECTED,
        )
        store = DjangoAdaptiveFrontierStore(
            feedback_store=self.base,
            policy=adaptive_policy(
                exploration_numerator=0,
                exploration_denominator=1,
            ),
        )

        claims = store.claim_sync(
            worker_id="exploit-worker",
            limit=2,
            lease_seconds=60,
            now=self.now,
        )

        self.assertEqual(
            [claim.target.target_key for claim in claims],
            [high.target_key, medium.target_key],
        )

    def test_expired_claim_can_be_recovered_by_adaptive_worker(self):
        target = self.admit("recover")
        first = self.store.claim_sync(
            worker_id="worker-a",
            limit=1,
            lease_seconds=1,
            now=self.now,
        )[0]

        later = self.now.replace(second=2)
        second = self.store.claim_sync(
            worker_id="worker-b",
            limit=1,
            lease_seconds=60,
            now=later,
        )[0]

        self.assertEqual(first.target.target_key, second.target.target_key)
        self.assertEqual(first.handoff_generation, second.handoff_generation)
        self.assertNotEqual(first.claim_token, second.claim_token)

    @skipUnless(POSTGRESQL, "adaptive concurrency contract requires PostgreSQL")
    def test_concurrent_workers_do_not_claim_same_target(self):
        for index in range(8):
            self.admit(f"concurrent-{index}")

        def claim(worker_id):
            close_old_connections()
            try:
                local_feedback = DjangoFeedbackStore()
                local_store = DjangoAdaptiveFrontierStore(
                    feedback_store=local_feedback,
                    policy=adaptive_policy(),
                )
                return {
                    item.target.target_key
                    for item in local_store.claim_sync(
                        worker_id=worker_id,
                        limit=5,
                        lease_seconds=60,
                        now=self.now,
                    )
                }
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(claim, "worker-a")
            second_future = executor.submit(claim, "worker-b")
            first = first_future.result()
            second = second_future.result()

        self.assertFalse(first & second)
        self.assertEqual(len(first | second), 8)
        self.assertEqual(
            ProspectorFrontierEntry.objects.filter(
                status=FrontierState.CLAIMED.value
            ).count(),
            8,
        )
