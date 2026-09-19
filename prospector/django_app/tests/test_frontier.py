from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import TestCase

from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_frontier import DjangoFrontierStore
from prospector.django_app.models import ProspectorFrontierEntry, ProspectorFrontierEvidence
from prospector.errors import FrontierClaimError
from prospector.frontier import FrontierState


class DjangoFrontierStoreTests(TestCase):
    def setUp(self):
        self.store = DjangoFrontierStore()
        self.now = datetime(2026, 9, 18, 9, 0, tzinfo=dt_timezone.utc)

    def candidate(
        self,
        locator="https://EXAMPLE.test:443/programs#section",
        *,
        method="external_index",
        source_target_key=None,
        policy_context=None,
    ):
        return ProspectingCandidate(
            locator=locator,
            kind="web_url",
            evidence=(
                ProspectingEvidence(
                    method=method,
                    discovered_at=self.now,
                    source_target_key=source_target_key,
                    provider="test-index" if method == "external_index" else None,
                    attributes={"relation": "candidate"},
                ),
            ),
            policy_context=policy_context or {"coverage": "test"},
            observation_hints={"expected_media_type": "text/html"},
        )

    def test_admission_canonicalizes_and_deduplicates_target(self):
        first = self.store.admit_sync(self.candidate())
        second = self.store.admit_sync(
            self.candidate(
                "https://example.test/programs",
                method="web_graph",
                source_target_key="web_url:v1:" + ("b" * 64),
            )
        )

        self.assertEqual(first.target_key, second.target_key)
        entry = ProspectorFrontierEntry.objects.get()
        self.assertEqual(entry.locator, "https://example.test/programs")
        self.assertEqual(entry.discovery_count, 2)
        self.assertEqual(ProspectorFrontierEvidence.objects.count(), 2)

    def test_repeated_identical_evidence_is_compacted(self):
        candidate = self.candidate()
        self.store.admit_sync(candidate)
        self.store.admit_sync(candidate)

        row = ProspectorFrontierEvidence.objects.get()
        self.assertEqual(row.discovery_count, 2)
        self.assertEqual(ProspectorFrontierEntry.objects.get().discovery_count, 2)

    def test_claim_complete_and_rediscovery_do_not_reactivate_target(self):
        target = self.store.admit_sync(self.candidate())
        claim = self.store.claim_sync(
            worker_id="worker-a",
            limit=1,
            lease_seconds=60,
            now=self.now,
        )[0]
        self.store.complete_sync(claim, now=self.now + timedelta(seconds=10))

        entry = ProspectorFrontierEntry.objects.get(target_key=target.target_key)
        self.assertEqual(entry.status, FrontierState.COMPLETED.value)
        self.assertIsNotNone(entry.completed_at)

        self.store.admit_sync(
            self.candidate("https://example.test/programs#rediscovered")
        )
        entry.refresh_from_db()
        self.assertEqual(entry.status, FrontierState.COMPLETED.value)
        self.assertEqual(entry.discovery_count, 2)

    def test_expired_lease_can_be_reclaimed_with_a_new_token(self):
        self.store.admit_sync(self.candidate())
        first = self.store.claim_sync(
            worker_id="worker-a",
            limit=1,
            lease_seconds=60,
            now=self.now,
        )[0]
        second = self.store.claim_sync(
            worker_id="worker-b",
            limit=1,
            lease_seconds=60,
            now=self.now + timedelta(seconds=61),
        )[0]

        self.assertNotEqual(first.claim_token, second.claim_token)
        self.assertEqual(second.worker_id, "worker-b")
        with self.assertRaises(FrontierClaimError):
            self.store.complete_sync(first, now=self.now + timedelta(seconds=62))

    def test_defer_respects_available_at(self):
        self.store.admit_sync(self.candidate())
        claim = self.store.claim_sync(
            worker_id="worker-a",
            limit=1,
            lease_seconds=60,
            now=self.now,
        )[0]
        future = self.now + timedelta(hours=2)
        self.store.defer_sync(claim, available_at=future)

        self.assertEqual(
            self.store.claim_sync(
                worker_id="worker-b",
                limit=1,
                now=self.now + timedelta(hours=1),
            ),
            (),
        )
        later = self.store.claim_sync(
            worker_id="worker-b",
            limit=1,
            now=future,
        )
        self.assertEqual(len(later), 1)

    def test_requeue_requires_target_not_to_be_actively_claimed(self):
        target = self.store.admit_sync(self.candidate())
        claim = self.store.claim_sync(worker_id="worker-a", limit=1, now=self.now)[0]
        with self.assertRaises(FrontierClaimError):
            self.store.requeue_sync(
                target_key=target.target_key,
                available_at=self.now,
            )

        self.store.complete_sync(claim, now=self.now + timedelta(seconds=1))
        requeued = self.store.requeue_sync(
            target_key=target.target_key,
            available_at=self.now + timedelta(minutes=1),
        )
        self.assertEqual(requeued.target_key, target.target_key)
        entry = ProspectorFrontierEntry.objects.get(target_key=target.target_key)
        self.assertEqual(entry.status, FrontierState.READY.value)
        self.assertIsNone(entry.completed_at)
        self.assertEqual(entry.handoff_generation, 2)


    def test_defer_and_expired_reclaim_keep_same_handoff_generation(self):
        self.store.admit_sync(self.candidate())
        first = self.store.claim_sync(
            worker_id="worker-a",
            limit=1,
            lease_seconds=60,
            now=self.now,
        )[0]
        self.assertEqual(first.handoff_generation, 1)

        future = self.now + timedelta(minutes=5)
        self.store.defer_sync(first, available_at=future)
        second = self.store.claim_sync(
            worker_id="worker-b",
            limit=1,
            lease_seconds=60,
            now=future,
        )[0]
        self.assertEqual(second.handoff_generation, 1)

        reclaimed = self.store.claim_sync(
            worker_id="worker-c",
            limit=1,
            lease_seconds=60,
            now=future + timedelta(seconds=61),
        )[0]
        self.assertEqual(reclaimed.handoff_generation, 1)


    def test_suppress_is_durable_and_rediscovery_does_not_reactivate(self):
        target = self.store.admit_sync(self.candidate())
        claim = self.store.claim_sync(
            worker_id="worker-a",
            limit=1,
            now=self.now,
        )[0]
        self.store.suppress_sync(
            claim,
            reason_code="security.non_global_address",
            now=self.now + timedelta(seconds=1),
        )

        entry = ProspectorFrontierEntry.objects.get(target_key=target.target_key)
        self.assertEqual(entry.status, FrontierState.SUPPRESSED.value)
        self.assertEqual(entry.suppression_reason, "security.non_global_address")
        self.assertIsNotNone(entry.suppressed_at)

        self.store.admit_sync(self.candidate())
        entry.refresh_from_db()
        self.assertEqual(entry.status, FrontierState.SUPPRESSED.value)

        self.store.requeue_sync(
            target_key=target.target_key,
            available_at=self.now + timedelta(minutes=1),
        )
        entry.refresh_from_db()
        self.assertEqual(entry.status, FrontierState.READY.value)
        self.assertEqual(entry.suppression_reason, "")
        self.assertIsNone(entry.suppressed_at)
        self.assertEqual(entry.handoff_generation, 2)
