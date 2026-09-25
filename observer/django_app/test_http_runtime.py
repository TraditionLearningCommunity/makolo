from __future__ import annotations

import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.db import IntegrityError, close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from prospector.observation_contracts import ObservationTarget, make_handoff_key

from observer.contracts import ObservationOutcome
from observer.django_artifacts import read_artifact_bytes
from observer.django_http_state import (
    cache_robots,
    get_cached_robots,
    release_host_lease,
    renew_host_lease,
    reserve_host_request,
)
from observer.django_runtime import claim_observations, execute_claim
from observer.django_store import absorb_observation_target
from observer.errors import ObserverStateConflictError
from observer.http_contracts import ScopeDeferred
from observer.runtime_contracts import (
    AcquiredArtifact,
    AcquisitionResult,
    ObserverRuntimePolicy,
)
from observer.testing import FakeAcquisition

from .models import (
    Observation,
    ObservedArtifact,
    ObserverScopeState,
)


class ObserverHttpRuntimePersistenceTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(
            MAKOLO_OBSERVER_ARTIFACT_ROOT=(
                Path(self.temp_dir.name) / "observer-artifacts"
            )
        )
        self.override.enable()
        self.now = datetime(2026, 9, 20, 13, 0, tzinfo=timezone.utc)
        self.target_key = "web_url:v1:" + ("e" * 64)
        self.policy = ObserverRuntimePolicy(
            profile_key="public-http",
            profile_fingerprint="public-http:test",
            policy_fingerprint="observer-http:test",
            lease_seconds=120,
            recovery_retry_seconds=30,
            watch_interval_seconds=300,
        )

    def tearDown(self):
        self.override.disable()
        self.temp_dir.cleanup()
        super().tearDown()

    def target(self, generation=1):
        return ObservationTarget(
            handoff_key=make_handoff_key(
                target_key=self.target_key,
                handoff_generation=generation,
            ),
            target_key=self.target_key,
            handoff_generation=generation,
            locator="https://example.test/resource",
            kind="web_url",
            requested_at=self.now + timedelta(seconds=generation),
            observation_hints={},
        )

    def absorb(self, generation=1):
        return absorb_observation_target(
            self.target(generation),
            absorbed_at=self.now + timedelta(seconds=10 + generation),
        )[0]

    def claim(self, *, now=None):
        claims = claim_observations(
            worker_id="observer-http-test",
            policy=self.policy,
            now=now or self.now + timedelta(seconds=20),
            limit=1,
        )
        self.assertEqual(len(claims), 1)
        return claims[0]

    def test_observed_http_result_persists_artifact_metrics_and_validators(self):
        self.absorb(1)
        claim = self.claim()
        captured_at = self.now + timedelta(seconds=21)
        payload = b"<!doctype html><html><body>raw</body></html>"
        acquisition = FakeAcquisition(
            lambda _claim: AcquisitionResult(
                outcome=ObservationOutcome.OBSERVED,
                observed_at=captured_at,
                final_locator="https://example.test/final",
                response_status=200,
                artifacts=(
                    AcquiredArtifact(
                        content=payload,
                        role="http_response_body",
                        captured_at=captured_at,
                        declared_media_type="text/html",
                        detected_media_type="text/html",
                        charset="utf-8",
                    ),
                ),
                validator_etag='"v1"',
                validator_last_modified=(
                    "Sun, 20 Sep 2026 12:00:00 GMT"
                ),
                redirect_count=2,
                wire_bytes=123,
                decoded_bytes=len(payload),
            )
        )

        observation = execute_claim(
            claim,
            acquisition=acquisition,
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
            completed_at=self.now + timedelta(seconds=22),
        )

        self.assertEqual(
            observation.outcome,
            ObservationOutcome.OBSERVED.value,
        )
        attempt = observation.attempts.get()
        self.assertEqual(attempt.redirect_count, 2)
        self.assertEqual(attempt.wire_bytes, 123)
        self.assertEqual(attempt.decoded_bytes, len(payload))
        self.assertEqual(
            attempt.final_locator,
            "https://example.test/final",
        )

        artifact = observation.artifacts.select_related("blob").get()
        self.assertEqual(artifact.role, "http_response_body")
        self.assertEqual(artifact.producing_attempt, attempt)
        self.assertEqual(
            read_artifact_bytes(artifact.artifact_ref),
            payload,
        )
        self.assertNotEqual(
            Path(artifact.blob.file.path).resolve().parent,
            Path(settings.MEDIA_ROOT).resolve(),
        )

        observation.series.refresh_from_db()
        self.assertEqual(observation.series.http_etag, '"v1"')
        self.assertEqual(
            observation.series.http_last_modified,
            "Sun, 20 Sep 2026 12:00:00 GMT",
        )
        self.assertEqual(
            observation.series.validator_artifact_ref,
            artifact.artifact_ref,
        )
        self.assertEqual(
            observation.series.watch_due_at,
            self.now + timedelta(seconds=322),
        )
        self.assertIsNone(observation.series.retry_due_at)

    def test_304_revalidates_prior_artifact_without_copying_blob(self):
        self.absorb(1)
        first_claim = self.claim()
        captured_at = self.now + timedelta(seconds=21)
        first = execute_claim(
            first_claim,
            acquisition=FakeAcquisition(
                lambda _claim: AcquisitionResult(
                    outcome=ObservationOutcome.OBSERVED,
                    observed_at=captured_at,
                    final_locator="https://example.test/resource",
                    response_status=200,
                    artifacts=(
                        AcquiredArtifact(
                            content=b"stable",
                            role="http_response_body",
                            captured_at=captured_at,
                        ),
                    ),
                    validator_etag='"v1"',
                    wire_bytes=6,
                    decoded_bytes=6,
                )
            ),
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
            completed_at=self.now + timedelta(seconds=22),
        )
        first_artifact = first.artifacts.get()
        self.absorb(2)

        second_claim = self.claim(
            now=self.now + timedelta(seconds=30)
        )
        second = execute_claim(
            second_claim,
            acquisition=FakeAcquisition(
                lambda _claim: AcquisitionResult(
                    outcome=ObservationOutcome.NOT_MODIFIED,
                    observed_at=self.now + timedelta(seconds=31),
                    final_locator="https://example.test/resource",
                    response_status=304,
                    revalidated_artifact_ref=first_artifact.artifact_ref,
                    validator_etag='"v2"',
                    wire_bytes=0,
                    decoded_bytes=0,
                )
            ),
            policy=self.policy,
            now=self.now + timedelta(seconds=30),
            completed_at=self.now + timedelta(seconds=32),
        )

        self.assertEqual(second.artifacts.count(), 0)
        self.assertEqual(
            list(
                second.revalidated_artifacts.values_list(
                    "artifact_ref",
                    flat=True,
                )
            ),
            [first_artifact.artifact_ref],
        )
        self.assertEqual(ObservedArtifact.objects.count(), 1)
        second.series.refresh_from_db()
        self.assertEqual(second.series.http_etag, '"v2"')
        self.assertEqual(
            second.series.validator_artifact_ref,
            first_artifact.artifact_ref,
        )

    def test_terminal_security_failure_does_not_schedule_retry(self):
        self.absorb(1)
        claim = self.claim()
        failed = execute_claim(
            claim,
            acquisition=FakeAcquisition(
                lambda _claim: AcquisitionResult(
                    outcome=ObservationOutcome.FAILED,
                    observed_at=self.now + timedelta(seconds=21),
                    failure_code="security.non_global_address",
                )
            ),
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
            completed_at=self.now + timedelta(seconds=22),
        )

        self.assertIsNone(failed.retry_at)
        failed.series.refresh_from_db()
        self.assertIsNone(failed.series.retry_due_at)
        self.assertIsNone(failed.series.watch_due_at)

    def test_new_explicit_handoff_clears_future_watch_timer_on_claim(self):
        self.absorb(1)
        first_claim = self.claim()
        first = execute_claim(
            first_claim,
            acquisition=FakeAcquisition(
                lambda _claim: AcquisitionResult(
                    outcome=ObservationOutcome.OBSERVED,
                    observed_at=self.now + timedelta(seconds=21),
                    response_status=204,
                )
            ),
            policy=self.policy,
            now=self.now + timedelta(seconds=20),
            completed_at=self.now + timedelta(seconds=22),
        )
        first.series.refresh_from_db()
        self.assertIsNotNone(first.series.watch_due_at)
        self.absorb(2)

        self.claim(now=self.now + timedelta(seconds=30))

        first.series.refresh_from_db()
        self.assertIsNone(first.series.watch_due_at)


class ObserverHttpScopeStateTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc)

    def test_scope_lease_enforces_interval_for_same_owner(self):
        lease = reserve_host_request(
            "example.test",
            now=self.now,
            min_interval_seconds=2,
            lease_seconds=30,
        )
        with self.assertRaises(ScopeDeferred) as ctx:
            renew_host_lease(
                lease,
                now=self.now + timedelta(seconds=1),
                min_interval_seconds=2,
                lease_seconds=30,
            )
        self.assertEqual(
            ctx.exception.retry_at,
            self.now + timedelta(seconds=2),
        )

        renewed = renew_host_lease(
            lease,
            now=self.now + timedelta(seconds=2),
            min_interval_seconds=2,
            lease_seconds=30,
        )
        self.assertEqual(renewed.token, lease.token)
        self.assertTrue(release_host_lease(renewed))

    def test_scope_active_lease_blocks_second_owner(self):
        reserve_host_request(
            "example.test",
            now=self.now,
            min_interval_seconds=0,
            lease_seconds=30,
        )

        with self.assertRaises(ScopeDeferred):
            reserve_host_request(
                "example.test",
                now=self.now + timedelta(seconds=1),
                min_interval_seconds=0,
                lease_seconds=30,
            )

    def test_robots_cache_expires(self):
        cache_robots(
            "https://example.test",
            status=200,
            body="User-agent: *\nAllow: /\n",
            checked_at=self.now,
            expires_at=self.now + timedelta(minutes=5),
        )

        self.assertIsNotNone(
            get_cached_robots(
                "https://example.test",
                now=self.now + timedelta(minutes=4),
            )
        )
        self.assertIsNone(
            get_cached_robots(
                "https://example.test",
                now=self.now + timedelta(minutes=6),
            )
        )

    def test_scope_database_rejects_half_lease(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ObserverScopeState.objects.create(
                    scope_kind="host",
                    scope_key="invalid.test",
                    lease_token="00000000-0000-0000-0000-000000000001",
                )


@skipUnless(
    connection.vendor == "postgresql",
    "Observer host-scope concurrency requires PostgreSQL",
)
class ObserverHttpScopePostgreSQLTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.now = datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc)

    def test_concurrent_workers_get_only_one_host_lease(self):
        barrier = threading.Barrier(2)
        leases = []
        deferred = []
        errors = []

        def run(index):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                lease = reserve_host_request(
                    "example.test",
                    now=self.now,
                    min_interval_seconds=0,
                    lease_seconds=30,
                )
                leases.append((index, lease))
            except ScopeDeferred as exc:
                deferred.append((index, exc.retry_at))
            except Exception as exc:
                errors.append(exc)
            finally:
                # Worker threads own separate PostgreSQL connections. Close
                # them explicitly so Django can drop the test database.
                connections.close_all()

        threads = [
            threading.Thread(target=run, args=(0,)),
            threading.Thread(target=run, args=(1,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(len(leases), 1)
        self.assertEqual(len(deferred), 1)
        self.assertEqual(
            ObserverScopeState.objects.filter(
                scope_kind="host",
                scope_key="example.test",
                lease_token__isnull=False,
            ).count(),
            1,
        )
