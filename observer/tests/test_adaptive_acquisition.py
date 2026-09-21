from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase

from observer.adaptive_acquisition import (
    AdaptiveObservationPlan,
    needs_browser_render,
)
from observer.adaptive_contracts import AdaptiveAcquisitionPolicy
from observer.browser_contracts import BrowserAcquisitionPolicy
from observer.contracts import (
    ArtifactOrigin,
    AttemptStrategy,
    ObservationOutcome,
)
from observer.http_contracts import HttpAcquisitionPolicy
from observer.runtime_contracts import (
    AcquiredArtifact,
    AcquisitionResult,
    ObservationClaim,
)


class FakeStage:
    def __init__(self, strategy):
        self.strategy = strategy


class AdaptiveAcquisitionTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 21, 3, 0, tzinfo=timezone.utc)
        http = HttpAcquisitionPolicy(
            user_agent="MakoloObserver/1.0 Test",
            host_min_interval_seconds=0,
        )
        browser = BrowserAcquisitionPolicy(
            http_policy=http,
            playwright_version="test",
        )
        self.policy = AdaptiveAcquisitionPolicy(
            http_policy=http,
            browser_policy=browser,
            html_probe_bytes=4096,
        )
        self.claim = ObservationClaim(
            observation_ref="observer:observation:v1:adaptive",
            claim_token="claim-token",
            worker_id="worker-a",
            leased_until=self.now + timedelta(minutes=5),
            target_key="web_url:v1:" + ("a" * 64),
            kind="web_url",
            locator="https://example.test/",
            source_handoff_key="observation:v1:adaptive",
            source_handoff_generation=1,
        )

    def result(self, body, *, media_type="text/html", status=200):
        return AcquisitionResult(
            outcome=ObservationOutcome.OBSERVED,
            observed_at=self.now + timedelta(seconds=1),
            final_locator=self.claim.locator,
            response_status=status,
            artifacts=(
                AcquiredArtifact(
                    content=body,
                    role="http_response_body",
                    captured_at=self.now + timedelta(seconds=1),
                    origin=ArtifactOrigin.CAPTURED,
                    declared_media_type=media_type,
                ),
            ),
            wire_bytes=len(body),
            decoded_bytes=len(body),
        )

    def test_static_html_does_not_escalate(self):
        result = self.result(
            b"<!doctype html><html><body><a href='/x'>x</a></body></html>"
        )
        self.assertFalse(
            needs_browser_render(result, policy=self.policy)
        )

    def test_inline_executable_script_escalates(self):
        result = self.result(
            b"<html><body><script>document.body.dataset.ready='1'</script></body></html>"
        )
        self.assertTrue(
            needs_browser_render(result, policy=self.policy)
        )

    def test_external_executable_script_escalates(self):
        result = self.result(
            b"<html><head><script src='/app.js'></script></head></html>"
        )
        self.assertTrue(
            needs_browser_render(result, policy=self.policy)
        )

    def test_legacy_javascript_mime_escalates(self):
        result = self.result(
            b'<script type="application/x-javascript" src="/legacy.js"></script>'
        )
        self.assertTrue(
            needs_browser_render(result, policy=self.policy)
        )

    def test_json_ld_script_does_not_escalate(self):
        result = self.result(
            b'<script type="application/ld+json">{"@type":"Thing"}</script>'
        )
        self.assertFalse(
            needs_browser_render(result, policy=self.policy)
        )

    def test_non_html_response_never_escalates(self):
        result = self.result(
            b'{"script":"not markup"}',
            media_type="application/json",
        )
        self.assertFalse(
            needs_browser_render(result, policy=self.policy)
        )

    def test_failed_or_retryable_http_never_escalates(self):
        result = AcquisitionResult(
            outcome=ObservationOutcome.FAILED,
            observed_at=self.now,
            response_status=503,
            failure_code="http.server_error",
            retry_at=self.now + timedelta(minutes=1),
        )
        self.assertFalse(
            needs_browser_render(result, policy=self.policy)
        )

    def test_probe_is_bounded(self):
        policy = AdaptiveAcquisitionPolicy(
            http_policy=self.policy.http_policy,
            browser_policy=self.policy.browser_policy,
            html_probe_bytes=32,
        )
        body = b"<html><body>" + b"x" * 64 + b"<script src='/late.js'></script>"
        self.assertFalse(
            needs_browser_render(
                self.result(body),
                policy=policy,
            )
        )

    def test_plan_allows_at_most_http_then_browser(self):
        http_stage = FakeStage(AttemptStrategy.DIRECT_HTTP)
        browser_stage = FakeStage(AttemptStrategy.BROWSER_RENDER)
        plan = AdaptiveObservationPlan(
            policy=self.policy,
            http_acquisition=http_stage,
            browser_acquisition=browser_stage,
        )
        result = self.result(b"<script src='/app.js'></script>")

        self.assertIs(plan.initial_acquisition(self.claim), http_stage)
        self.assertIs(
            plan.next_acquisition(
                self.claim,
                previous_acquisition=http_stage,
                result=result,
            ),
            browser_stage,
        )
        self.assertIsNone(
            plan.next_acquisition(
                self.claim,
                previous_acquisition=browser_stage,
                result=result,
            )
        )

    def test_profile_changes_with_escalation_policy(self):
        smaller = AdaptiveAcquisitionPolicy(
            http_policy=self.policy.http_policy,
            browser_policy=self.policy.browser_policy,
            html_probe_bytes=2048,
        )
        self.assertNotEqual(
            smaller.profile_fingerprint,
            self.policy.profile_fingerprint,
        )
