from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from observer.browser_contracts import (
    BrowserAcquisitionPolicy,
    BrowserRenderFailure,
    BrowserRenderResult,
    BrowserResourceRequest,
)
from observer.http_contracts import HttpResourceFailure


_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_DROP_RESPONSE_HEADERS = frozenset(
    {
        "connection",
        "content-encoding",
        "content-length",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "set-cookie",
        "set-cookie2",
        "transfer-encoding",
        "upgrade",
        "www-authenticate",
        "alt-svc",
    }
)


def _remaining_seconds(
    *,
    deadline_at: datetime,
    clock,
) -> float:
    now = clock()
    remaining = (deadline_at - now).total_seconds()
    if remaining <= 0:
        raise BrowserRenderFailure(
            "browser.observation_timeout",
            retryable=True,
        )
    return remaining


def _safe_response_headers(headers) -> dict[str, str]:
    safe = {}
    for key, value in headers.items():
        name = str(key).lower()
        if name in _DROP_RESPONSE_HEADERS:
            continue
        safe[name] = str(value)
    return safe


class PlaywrightBrowserRenderer:
    """Render JavaScript while keeping Chromium off the external network.

    All HTTP(S) requests are intercepted at BrowserContext level and fulfilled
    from the Observer-owned safe resource loader. A loopback sink proxy is a
    second line of defence for any browser traffic not covered by routing.
    """

    def render(
        self,
        *,
        start_url: str,
        policy: BrowserAcquisitionPolicy,
        resource_loader,
        deadline_at: datetime,
        clock,
    ) -> BrowserRenderResult:
        main = {
            "status": None,
            "body": b"",
            "headers": {},
            "retry_at": None,
        }
        state = {
            "redirect_count": 0,
            "incomplete": False,
            "fatal": None,
            "network_requests": 0,
        }
        page_holder = {"page": None}

        def fail_main(exc) -> None:
            if state["fatal"] is None:
                state["fatal"] = exc

        def handle_route(route) -> None:
            request = route.request
            page = page_holder["page"]
            is_main = bool(
                page is not None
                and request.is_navigation_request()
                and request.frame == page.main_frame
            )
            resource_type = str(request.resource_type or "other").lower()
            method = str(request.method or "").upper()

            if resource_type in policy.blocked_resource_types:
                route.abort(error_code="blockedbyclient")
                return

            if method != "GET":
                state["incomplete"] = True
                if is_main:
                    fail_main(
                        BrowserRenderFailure(
                            "browser.unsafe_method",
                            retryable=False,
                        )
                    )
                route.abort(error_code="blockedbyclient")
                return

            if state["network_requests"] >= policy.max_requests:
                state["incomplete"] = True
                if is_main:
                    fail_main(
                        BrowserRenderFailure(
                            "browser.request_budget_exceeded",
                            retryable=False,
                        )
                    )
                route.abort(error_code="blockedbyclient")
                return

            state["network_requests"] += 1
            redirected_from = getattr(
                request,
                "redirected_from",
                None,
            )
            redirect_depth = 0
            cursor = redirected_from
            while cursor is not None:
                redirect_depth += 1
                cursor = getattr(cursor, "redirected_from", None)
            if redirect_depth > policy.http_policy.max_redirects:
                state["incomplete"] = True
                failure = BrowserRenderFailure(
                    "http.redirect_limit",
                    retryable=False,
                )
                if is_main:
                    fail_main(failure)
                route.abort(error_code="blockedbyclient")
                return
            if redirected_from is not None:
                previous_scheme = urlsplit(
                    redirected_from.url
                ).scheme.lower()
                current_scheme = urlsplit(request.url).scheme.lower()
                if (
                    previous_scheme == "https"
                    and current_scheme == "http"
                    and not policy.http_policy.allow_https_to_http_redirect
                ):
                    state["incomplete"] = True
                    failure = BrowserRenderFailure(
                        "security.redirect_downgrade",
                        retryable=False,
                    )
                    if is_main:
                        fail_main(failure)
                    route.abort(error_code="blockedbyclient")
                    return

            browser_request = BrowserResourceRequest(
                url=request.url,
                method=method,
                headers=request.headers,
                resource_type=resource_type,
                is_main_navigation=is_main,
            )
            try:
                result = resource_loader(browser_request)
            except HttpResourceFailure as exc:
                state["incomplete"] = True
                if is_main:
                    fail_main(
                        BrowserRenderFailure(
                            exc.code,
                            retryable=exc.retry_at is not None,
                            retry_at=exc.retry_at,
                            response_status=exc.response_status,
                        )
                    )
                route.abort(error_code="blockedbyclient")
                return

            headers = _safe_response_headers(result.headers)
            location = headers.get("location")
            if (
                result.status in _REDIRECT_STATUSES
                and location
            ):
                next_url = urljoin(result.response_url, location)
                next_scheme = urlsplit(next_url).scheme.lower()
                current_scheme = urlsplit(
                    result.response_url
                ).scheme.lower()
                if next_scheme not in {"http", "https"}:
                    state["incomplete"] = True
                    failure = BrowserRenderFailure(
                        "security.unsupported_redirect_scheme",
                        retryable=False,
                    )
                    if is_main:
                        fail_main(failure)
                    route.abort(error_code="blockedbyclient")
                    return
                if (
                    current_scheme == "https"
                    and next_scheme == "http"
                    and not policy.http_policy.allow_https_to_http_redirect
                ):
                    state["incomplete"] = True
                    failure = BrowserRenderFailure(
                        "security.redirect_downgrade",
                        retryable=False,
                    )
                    if is_main:
                        fail_main(failure)
                    route.abort(error_code="blockedbyclient")
                    return

            if (
                result.status in _REDIRECT_STATUSES
                and headers.get("location")
            ):
                state["redirect_count"] += 1
            elif is_main:
                main["status"] = result.status
                main["body"] = result.body
                main["headers"] = dict(result.headers)
                main["retry_at"] = result.retry_at

            route.fulfill(
                status=result.status,
                headers=headers,
                body=result.body,
            )

        def block_websocket(ws) -> None:
            ws.close(
                code=1008,
                reason="Observer public-browser policy blocks WebSocket",
            )

        init_script = """
(() => {
  const blocked = [
    'RTCPeerConnection',
    'webkitRTCPeerConnection',
    'WebTransport',
    'WebSocket'
  ];
  for (const name of blocked) {
    try {
      Object.defineProperty(globalThis, name, {
        value: undefined,
        writable: false,
        configurable: false
      });
    } catch (_) {}
  }
  try {
    Object.defineProperty(navigator, 'sendBeacon', {
      value: () => false,
      writable: false,
      configurable: false
    });
  } catch (_) {}
  try {
    Object.defineProperty(window, 'open', {
      value: () => null,
      writable: false,
      configurable: false
    });
  } catch (_) {}
})();
"""

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    proxy={"server": policy.sink_proxy},
                    args=[
                        "--disable-background-networking",
                        "--disable-component-update",
                        "--disable-default-apps",
                        "--disable-sync",
                        "--dns-prefetch-disable",
                        "--metrics-recording-only",
                        "--no-first-run",
                        "--safebrowsing-disable-auto-update",
                    ],
                )
                try:
                    context = browser.new_context(
                        user_agent=policy.http_policy.user_agent,
                        locale=policy.locale,
                        viewport={
                            "width": policy.viewport_width,
                            "height": policy.viewport_height,
                        },
                        java_script_enabled=True,
                        service_workers="block",
                        accept_downloads=False,
                        ignore_https_errors=False,
                    )
                    try:
                        context.add_init_script(script=init_script)
                        context.route_web_socket("**", block_websocket)
                        context.route("**/*", handle_route)

                        page = context.new_page()
                        page_holder["page"] = page
                        page.set_default_timeout(
                            max(
                                1,
                                int(
                                    _remaining_seconds(
                                        deadline_at=deadline_at,
                                        clock=clock,
                                    )
                                    * 1000
                                ),
                            )
                        )
                        page.set_default_navigation_timeout(
                            max(
                                1,
                                int(
                                    _remaining_seconds(
                                        deadline_at=deadline_at,
                                        clock=clock,
                                    )
                                    * 1000
                                ),
                            )
                        )

                        try:
                            page.goto(
                                start_url,
                                wait_until="domcontentloaded",
                                timeout=max(
                                    1,
                                    int(
                                        _remaining_seconds(
                                            deadline_at=deadline_at,
                                            clock=clock,
                                        )
                                        * 1000
                                    ),
                                ),
                            )
                        except PlaywrightTimeoutError as exc:
                            if state["fatal"] is not None:
                                raise state["fatal"] from exc
                            raise BrowserRenderFailure(
                                "browser.navigation_timeout",
                                retryable=True,
                            ) from exc
                        except PlaywrightError as exc:
                            if state["fatal"] is not None:
                                raise state["fatal"] from exc
                            raise BrowserRenderFailure(
                                "browser.navigation_error",
                                retryable=True,
                            ) from exc

                        if state["fatal"] is not None:
                            raise state["fatal"]

                        remaining = _remaining_seconds(
                            deadline_at=deadline_at,
                            clock=clock,
                        )
                        settle = min(
                            float(policy.settle_timeout_seconds),
                            remaining,
                        )
                        if settle > 0:
                            try:
                                page.wait_for_load_state(
                                    "load",
                                    timeout=max(1, int(settle * 1000)),
                                )
                            except PlaywrightTimeoutError:
                                state["incomplete"] = True

                        if state["fatal"] is not None:
                            raise state["fatal"]
                        final_locator = page.url
                        if urlsplit(final_locator).scheme not in {
                            "http",
                            "https",
                        }:
                            raise BrowserRenderFailure(
                                "browser.non_http_final_locator",
                                retryable=False,
                            )
                        if main["status"] is None:
                            raise BrowserRenderFailure(
                                "browser.main_response_missing",
                                retryable=True,
                            )
                        try:
                            rendered_dom = page.content().encode("utf-8")
                        except PlaywrightError as exc:
                            raise BrowserRenderFailure(
                                "browser.dom_capture_failed",
                                retryable=True,
                            ) from exc

                        return BrowserRenderResult(
                            final_locator=final_locator,
                            response_status=main["status"],
                            rendered_dom=rendered_dom,
                            main_response_body=main["body"],
                            main_response_headers=main["headers"],
                            redirect_count=state["redirect_count"],
                            incomplete=state["incomplete"],
                            retry_at=main["retry_at"],
                        )
                    finally:
                        context.close()
                finally:
                    browser.close()
        except BrowserRenderFailure:
            raise
        except PlaywrightError as exc:
            raise BrowserRenderFailure(
                "browser.runtime_error",
                retryable=True,
            ) from exc
