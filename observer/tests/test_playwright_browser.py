from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest import TestCase, skipUnless

from observer.adapters.playwright_browser import PlaywrightBrowserRenderer
from observer.browser_contracts import BrowserAcquisitionPolicy
from observer.http_contracts import (
    HttpAcquisitionPolicy,
    SafeHttpResourceResult,
)


def _clock():
    return datetime.now(timezone.utc)


@skipUnless(
    os.environ.get("MAKOLO_OBSERVER_BROWSER_INTEGRATION") == "1",
    "Chromium integration is enabled only in the Observer browser CI gate",
)
class PlaywrightBrowserRendererIntegrationTests(TestCase):
    def setUp(self):
        self.policy = BrowserAcquisitionPolicy(
            http_policy=HttpAcquisitionPolicy(
                user_agent="MakoloObserver/1.0 BrowserIntegration",
                host_min_interval_seconds=0,
            ),
        )
        self.renderer = PlaywrightBrowserRenderer()

    def test_inline_javascript_renders_without_external_browser_network(self):
        html = b"""<!doctype html>
<html><body><main id="result">shell</main>
<script>
document.querySelector('#result').textContent = 'rendered';
document.body.dataset.websocket =
  typeof WebSocket === 'undefined' ? 'blocked' : 'open';
document.body.dataset.webrtc =
  typeof RTCPeerConnection === 'undefined' ? 'blocked' : 'open';
</script></body></html>"""

        def loader(request):
            self.assertEqual(request.url, "https://example.test/app")
            return SafeHttpResourceResult(
                requested_url=request.url,
                response_url=request.url,
                status=200,
                headers={"content-type": "text/html; charset=utf-8"},
                body=html,
                wire_bytes=len(html),
                decoded_bytes=len(html),
            )

        result = self.renderer.render(
            start_url="https://example.test/app",
            policy=self.policy,
            resource_loader=loader,
            deadline_at=_clock() + timedelta(seconds=30),
            clock=_clock,
        )

        dom = result.rendered_dom.decode("utf-8")
        self.assertIn(">rendered<", dom)
        self.assertIn('data-websocket="blocked"', dom)
        self.assertIn('data-webrtc="blocked"', dom)
        self.assertEqual(result.response_status, 200)
        self.assertFalse(result.incomplete)

    def test_external_script_is_fulfilled_from_observer_loader(self):
        html = (
            b"<!doctype html><html><body><main id='result'>shell</main>"
            b"<script src='/app.js'></script></body></html>"
        )
        script = (
            b"document.querySelector('#result').textContent = 'from-script';"
        )
        seen = []

        def loader(request):
            seen.append(request.url)
            if request.url == "https://example.test/app":
                body = html
                media = "text/html"
            elif request.url == "https://example.test/app.js":
                body = script
                media = "application/javascript"
            else:
                self.fail(f"unexpected routed URL {request.url}")
            return SafeHttpResourceResult(
                requested_url=request.url,
                response_url=request.url,
                status=200,
                headers={"content-type": media},
                body=body,
                wire_bytes=len(body),
                decoded_bytes=len(body),
            )

        result = self.renderer.render(
            start_url="https://example.test/app",
            policy=self.policy,
            resource_loader=loader,
            deadline_at=_clock() + timedelta(seconds=30),
            clock=_clock,
        )

        self.assertIn(
            ">from-script<",
            result.rendered_dom.decode("utf-8"),
        )
        self.assertEqual(
            seen,
            [
                "https://example.test/app",
                "https://example.test/app.js",
            ],
        )

    def test_https_to_http_redirect_is_blocked_before_browser_network(self):
        def loader(request):
            return SafeHttpResourceResult(
                requested_url=request.url,
                response_url=request.url,
                status=302,
                headers={"location": "http://example.test/insecure"},
                body=b"",
                wire_bytes=0,
                decoded_bytes=0,
            )

        with self.assertRaisesRegex(
            Exception,
            "security.redirect_downgrade",
        ):
            self.renderer.render(
                start_url="https://example.test/app",
                policy=self.policy,
                resource_loader=loader,
                deadline_at=_clock() + timedelta(seconds=30),
                clock=_clock,
            )
