from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase

from observer.browser_acquisition import BrowserRenderAcquisition
from observer.browser_contracts import (
    BrowserAcquisitionPolicy,
    BrowserRenderFailure,
    BrowserRenderResult,
    BrowserResourceRequest,
)
from observer.contracts import (
    ArtifactCompleteness,
    ArtifactOrigin,
    ObservationOutcome,
)
from observer.http_contracts import (
    HttpAcquisitionPolicy,
    SafeHttpResourceResult,
)
from observer.runtime_contracts import ObservationClaim


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 9, 21, 1, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


class FakeSession:
    def __init__(self, response=None):
        self.response = response
        self.stats = SimpleNamespace(wire_bytes=0, decoded_bytes=0)
        self.closed = False
        self.calls = []

    def fetch(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.response
        if response is None:
            raise AssertionError("unexpected resource fetch")
        self.stats.wire_bytes += response.wire_bytes
        self.stats.decoded_bytes += response.decoded_bytes
        return response

    def close(self):
        self.closed = True


class FakeHttpAcquisition:
    def __init__(self, session):
        self.session = session
        self.deadlines = []

    def open_resource_session(self, *, deadline_at):
        self.deadlines.append(deadline_at)
        return self.session


class StaticRenderer:
    def __init__(self, result=None, failure=None, call_loader=False):
        self.result = result
        self.failure = failure
        self.call_loader = call_loader

    def render(self, **kwargs):
        if self.call_loader:
            kwargs["resource_loader"](
                BrowserResourceRequest(
                    url=kwargs["start_url"],
                    method="GET",
                    headers={"accept": "text/html"},
                    resource_type="document",
                    is_main_navigation=True,
                )
            )
        if self.failure is not None:
            raise self.failure
        return self.result


class BrowserRenderAcquisitionTests(TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.http_policy = HttpAcquisitionPolicy(
            user_agent="MakoloObserver/1.0 BrowserTest",
            host_min_interval_seconds=0,
        )
        self.policy = BrowserAcquisitionPolicy(
            http_policy=self.http_policy,
            playwright_version="test",
        )
        self.claim = ObservationClaim(
            observation_ref="observer:observation:v1:browser",
            claim_token="claim-token",
            worker_id="worker-browser",
            leased_until=self.clock() + timedelta(minutes=5),
            target_key="web_url:v1:" + ("b" * 64),
            kind="web_url",
            locator="https://example.test/app",
            source_handoff_key="observation:v1:browser",
            source_handoff_generation=1,
        )

    def render_result(self, **overrides):
        values = {
            "final_locator": "https://example.test/app",
            "response_status": 200,
            "rendered_dom": b"<html><body>rendered</body></html>",
            "main_response_body": b"<html><body>shell</body></html>",
            "main_response_headers": {
                "content-type": "text/html; charset=utf-8"
            },
            "redirect_count": 0,
            "incomplete": False,
            "retry_at": None,
        }
        values.update(overrides)
        return BrowserRenderResult(**values)

    def acquisition(self, renderer, session=None, policy=None):
        session = session or FakeSession()
        return BrowserRenderAcquisition(
            policy=policy or self.policy,
            http_acquisition=FakeHttpAcquisition(session),
            renderer=renderer,
            clock=self.clock,
        ), session

    def test_success_persists_raw_main_and_rendered_dom_artifacts(self):
        acquisition, session = self.acquisition(
            StaticRenderer(self.render_result())
        )

        result = acquisition.acquire(self.claim)

        self.assertEqual(result.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(result.response_status, 200)
        self.assertEqual(len(result.artifacts), 2)
        raw, rendered = result.artifacts
        self.assertEqual(raw.role, "browser_main_response_body")
        self.assertEqual(raw.origin, ArtifactOrigin.CAPTURED)
        self.assertEqual(raw.declared_media_type, "text/html")
        self.assertEqual(rendered.role, "rendered_dom")
        self.assertEqual(rendered.origin, ArtifactOrigin.RENDERED)
        self.assertEqual(
            rendered.completeness,
            ArtifactCompleteness.COMPLETE,
        )
        self.assertTrue(session.closed)

    def test_incomplete_render_marks_rendered_artifact_incomplete(self):
        acquisition, _session = self.acquisition(
            StaticRenderer(
                self.render_result(incomplete=True)
            )
        )

        result = acquisition.acquire(self.claim)

        rendered = result.artifacts[-1]
        self.assertEqual(
            rendered.completeness,
            ArtifactCompleteness.INCOMPLETE,
        )

    def test_large_dom_is_truncated_explicitly(self):
        policy = BrowserAcquisitionPolicy(
            http_policy=self.http_policy,
            playwright_version="test",
            max_rendered_dom_bytes=8,
        )
        acquisition, _session = self.acquisition(
            StaticRenderer(
                self.render_result(rendered_dom=b"0123456789abcdef")
            ),
            policy=policy,
        )

        result = acquisition.acquire(self.claim)

        rendered = result.artifacts[-1]
        self.assertEqual(rendered.content, b"01234567")
        self.assertEqual(
            rendered.completeness,
            ArtifactCompleteness.TRUNCATED,
        )
        self.assertIsNone(rendered.charset)

    def test_retryable_main_status_fails_with_retry_at(self):
        retry_at = self.clock() + timedelta(seconds=90)
        acquisition, _session = self.acquisition(
            StaticRenderer(
                self.render_result(
                    response_status=429,
                    retry_at=retry_at,
                )
            )
        )

        result = acquisition.acquire(self.claim)

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(result.failure_code, "http.rate_limited")
        self.assertEqual(result.retry_at, retry_at)
        self.assertEqual(result.artifacts, ())

    def test_retryable_browser_failure_gets_bounded_retry(self):
        acquisition, session = self.acquisition(
            StaticRenderer(
                failure=BrowserRenderFailure(
                    "browser.navigation_timeout",
                    retryable=True,
                )
            )
        )

        result = acquisition.acquire(self.claim)

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(
            result.failure_code,
            "browser.navigation_timeout",
        )
        self.assertEqual(
            result.retry_at,
            self.clock() + timedelta(
                seconds=self.http_policy.retry_seconds
            ),
        )
        self.assertTrue(session.closed)

    def test_resource_loader_applies_total_budget(self):
        response = SafeHttpResourceResult(
            requested_url="https://example.test/app",
            response_url="https://example.test/app",
            status=200,
            headers={"content-type": "text/html"},
            body=b"1234",
            wire_bytes=4,
            decoded_bytes=4,
        )
        session = FakeSession(response)
        policy = BrowserAcquisitionPolicy(
            http_policy=self.http_policy,
            playwright_version="test",
            max_total_wire_bytes=4,
            max_total_decoded_bytes=4,
        )
        acquisition, _session = self.acquisition(
            StaticRenderer(
                self.render_result(),
                call_loader=True,
            ),
            session=session,
            policy=policy,
        )

        result = acquisition.acquire(self.claim)

        self.assertEqual(result.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(result.wire_bytes, 4)
        self.assertEqual(result.decoded_bytes, 4)
        call = session.calls[0][1]
        self.assertEqual(call["max_wire_bytes"], 4)
        self.assertEqual(call["max_decoded_bytes"], 4)

    def test_browser_profile_changes_when_renderer_version_changes(self):
        other = BrowserAcquisitionPolicy(
            http_policy=self.http_policy,
            playwright_version="different",
        )

        self.assertNotEqual(
            self.policy.profile_fingerprint,
            other.profile_fingerprint,
        )
