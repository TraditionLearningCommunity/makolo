from __future__ import annotations

from datetime import datetime, timedelta, timezone

from django.test import TestCase

from prospector.observation_contracts import ObservationTarget, make_handoff_key

from observer.adaptive_acquisition import AdaptiveObservationPlan
from observer.adaptive_contracts import AdaptiveAcquisitionPolicy
from observer.browser_contracts import BrowserAcquisitionPolicy
from observer.contracts import (
    ArtifactOrigin,
    AttemptStrategy,
    ObservationOutcome,
)
from observer.django_runtime import claim_observations, execute_claim
from observer.django_store import absorb_observation_target
from observer.http_contracts import HttpAcquisitionPolicy
from observer.runtime_contracts import (
    AcquiredArtifact,
    AcquisitionResult,
    ObserverRuntimePolicy,
)

from .models import Observation


class Stage:
    def __init__(self, strategy, result_factory):
        self.strategy = strategy
        self.result_factory = result_factory
        self.calls = 0

    def acquire(self, claim):
        self.calls += 1
        return self.result_factory(claim)


class AdaptiveRuntimeTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 21, 3, 0, tzinfo=timezone.utc)
        self.target_key = "web_url:v1:" + ("7" * 64)
        target = ObservationTarget(
            handoff_key=make_handoff_key(
                target_key=self.target_key,
                handoff_generation=1,
            ),
            target_key=self.target_key,
            handoff_generation=1,
            locator="https://example.test/resource",
            kind="web_url",
            requested_at=self.now,
            observation_hints={},
        )
        absorb_observation_target(
            target,
            absorbed_at=self.now + timedelta(seconds=1),
        )
        http = HttpAcquisitionPolicy(
            user_agent="MakoloObserver/1.0 Test",
            host_min_interval_seconds=0,
        )
        browser = BrowserAcquisitionPolicy(
            http_policy=http,
            playwright_version="test",
        )
        self.adaptive = AdaptiveAcquisitionPolicy(
            http_policy=http,
            browser_policy=browser,
        )
        self.runtime_policy = ObserverRuntimePolicy(
            profile_key=self.adaptive.profile_key,
            profile_fingerprint=self.adaptive.profile_fingerprint,
            policy_fingerprint=self.adaptive.policy_fingerprint,
            lease_seconds=300,
            recovery_retry_seconds=30,
        )

    def claim(self):
        claims = claim_observations(
            worker_id="adaptive-worker",
            policy=self.runtime_policy,
            now=self.now + timedelta(seconds=2),
            limit=1,
        )
        self.assertEqual(len(claims), 1)
        return claims[0]

    def http_result(self, claim, body):
        return AcquisitionResult(
            outcome=ObservationOutcome.OBSERVED,
            observed_at=self.now + timedelta(seconds=3),
            final_locator=claim.locator,
            response_status=200,
            artifacts=(
                AcquiredArtifact(
                    content=body,
                    role="http_response_body",
                    captured_at=self.now + timedelta(seconds=3),
                    origin=ArtifactOrigin.CAPTURED,
                    declared_media_type="text/html",
                ),
            ),
            wire_bytes=len(body),
            decoded_bytes=len(body),
        )

    def browser_result(self, claim):
        dom = b"<html><body data-rendered='1'></body></html>"
        return AcquisitionResult(
            outcome=ObservationOutcome.OBSERVED,
            observed_at=self.now + timedelta(seconds=4),
            final_locator=claim.locator,
            response_status=200,
            artifacts=(
                AcquiredArtifact(
                    content=dom,
                    role="rendered_dom",
                    captured_at=self.now + timedelta(seconds=4),
                    origin=ArtifactOrigin.RENDERED,
                    declared_media_type="text/html",
                    detected_media_type="text/html",
                    charset="utf-8",
                ),
            ),
            wire_bytes=10,
            decoded_bytes=10,
        )

    def test_dynamic_html_persists_http_then_browser_as_two_attempts(self):
        claim = self.claim()
        body = b"<html><script src='/app.js'></script></html>"
        http_stage = Stage(
            AttemptStrategy.DIRECT_HTTP,
            lambda current: self.http_result(current, body),
        )
        browser_stage = Stage(
            AttemptStrategy.BROWSER_RENDER,
            self.browser_result,
        )
        plan = AdaptiveObservationPlan(
            policy=self.adaptive,
            http_acquisition=http_stage,
            browser_acquisition=browser_stage,
        )

        observation = execute_claim(
            claim,
            acquisition=plan,
            policy=self.runtime_policy,
            now=self.now + timedelta(seconds=2),
            completed_at=self.now + timedelta(seconds=5),
        )

        self.assertEqual(
            observation.outcome,
            ObservationOutcome.OBSERVED.value,
        )
        attempts = list(observation.attempts.order_by("ordinal"))
        self.assertEqual(len(attempts), 2)
        self.assertEqual(
            [item.strategy for item in attempts],
            ["direct_http", "browser_render"],
        )
        artifacts = list(observation.artifacts.order_by("captured_at"))
        self.assertEqual(
            [item.role for item in artifacts],
            ["http_response_body", "rendered_dom"],
        )
        self.assertEqual(
            artifacts[0].producing_attempt_id,
            attempts[0].id,
        )
        self.assertEqual(
            artifacts[1].producing_attempt_id,
            attempts[1].id,
        )

    def test_static_html_finishes_after_direct_http_attempt(self):
        claim = self.claim()
        body = b"<html><body>static</body></html>"
        http_stage = Stage(
            AttemptStrategy.DIRECT_HTTP,
            lambda current: self.http_result(current, body),
        )
        browser_stage = Stage(
            AttemptStrategy.BROWSER_RENDER,
            self.browser_result,
        )
        plan = AdaptiveObservationPlan(
            policy=self.adaptive,
            http_acquisition=http_stage,
            browser_acquisition=browser_stage,
        )

        observation = execute_claim(
            claim,
            acquisition=plan,
            policy=self.runtime_policy,
            now=self.now + timedelta(seconds=2),
            completed_at=self.now + timedelta(seconds=5),
        )

        self.assertEqual(observation.attempts.count(), 1)
        self.assertEqual(browser_stage.calls, 0)
        self.assertEqual(observation.artifacts.count(), 1)

    def test_browser_success_preserves_http_validator_baseline(self):
        claim = self.claim()
        body = b"<script src='/app.js'></script>"
        http_stage = Stage(
            AttemptStrategy.DIRECT_HTTP,
            lambda current: AcquisitionResult(
                outcome=ObservationOutcome.OBSERVED,
                observed_at=self.now + timedelta(seconds=3),
                final_locator=current.locator,
                response_status=200,
                artifacts=(
                    AcquiredArtifact(
                        content=body,
                        role="http_response_body",
                        captured_at=self.now + timedelta(seconds=3),
                        origin=ArtifactOrigin.CAPTURED,
                        declared_media_type="text/html",
                    ),
                ),
                validator_etag='"adaptive-v1"',
                validator_last_modified=(
                    "Mon, 21 Sep 2026 03:00:00 GMT"
                ),
                wire_bytes=len(body),
                decoded_bytes=len(body),
            ),
        )
        browser_stage = Stage(
            AttemptStrategy.BROWSER_RENDER,
            self.browser_result,
        )
        plan = AdaptiveObservationPlan(
            policy=self.adaptive,
            http_acquisition=http_stage,
            browser_acquisition=browser_stage,
        )

        observation = execute_claim(
            claim,
            acquisition=plan,
            policy=self.runtime_policy,
            now=self.now + timedelta(seconds=2),
            completed_at=self.now + timedelta(seconds=5),
        )

        observation.series.refresh_from_db()
        http_artifact = observation.artifacts.get(
            role="http_response_body"
        )
        self.assertEqual(
            observation.series.http_etag,
            '"adaptive-v1"',
        )
        self.assertEqual(
            observation.series.http_last_modified,
            "Mon, 21 Sep 2026 03:00:00 GMT",
        )
        self.assertEqual(
            observation.series.validator_artifact_ref,
            http_artifact.artifact_ref,
        )

    def test_browser_failure_keeps_successful_http_provenance(self):
        claim = self.claim()
        body = b"<script src='/app.js'></script>"
        http_stage = Stage(
            AttemptStrategy.DIRECT_HTTP,
            lambda current: self.http_result(current, body),
        )
        browser_stage = Stage(
            AttemptStrategy.BROWSER_RENDER,
            lambda _current: AcquisitionResult(
                outcome=ObservationOutcome.FAILED,
                observed_at=self.now + timedelta(seconds=4),
                failure_code="browser.render_timeout",
                retry_at=self.now + timedelta(minutes=1),
            ),
        )
        plan = AdaptiveObservationPlan(
            policy=self.adaptive,
            http_acquisition=http_stage,
            browser_acquisition=browser_stage,
        )

        observation = execute_claim(
            claim,
            acquisition=plan,
            policy=self.runtime_policy,
            now=self.now + timedelta(seconds=2),
            completed_at=self.now + timedelta(seconds=5),
        )

        observation.refresh_from_db()
        self.assertEqual(
            observation.outcome,
            ObservationOutcome.FAILED.value,
        )
        self.assertEqual(
            observation.failure_code,
            "browser.render_timeout",
        )
        self.assertEqual(observation.attempts.count(), 2)
        self.assertEqual(observation.artifacts.count(), 1)
        self.assertEqual(
            observation.artifacts.get().role,
            "http_response_body",
        )
        observation.series.refresh_from_db()
        self.assertEqual(
            observation.series.retry_due_at,
            self.now + timedelta(minutes=1),
        )
        http_artifact = observation.artifacts.get(
            role="http_response_body"
        )
        self.assertEqual(
            observation.series.validator_artifact_ref,
            http_artifact.artifact_ref,
        )
