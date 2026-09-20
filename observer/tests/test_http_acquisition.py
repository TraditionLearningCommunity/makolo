from __future__ import annotations

import gzip
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from observer.contracts import ObservationOutcome
from observer.http_acquisition import DirectHttpAcquisition
from observer.http_contracts import (
    HostLease,
    HttpAcquisitionPolicy,
    HttpExchange,
    HttpObservationContext,
    HttpTransportFailure,
    RobotsCache,
    ScopeDeferred,
)
from observer.runtime_contracts import ObservationClaim


GLOBAL_IP = "93.184.216.34"
OTHER_GLOBAL_IP = "1.1.1.1"


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += timedelta(seconds=seconds)


class FakeResolver:
    def __init__(self, answers=None):
        self.answers = {
            key: list(value)
            for key, value in (answers or {}).items()
        }
        self.calls = []

    def resolve(self, hostname):
        self.calls.append(hostname)
        configured = self.answers.get(hostname)
        if not configured:
            return (GLOBAL_IP,)
        if len(configured) > 1:
            return tuple(configured.pop(0))
        return tuple(configured[0])


class FakeTransport:
    def __init__(self, responses):
        self.responses = {
            key: list(value)
            for key, value in responses.items()
        }
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        queue = self.responses.get(kwargs["url"])
        if not queue:
            raise AssertionError(
                f"unexpected HTTP request {kwargs['url']}"
            )
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeScopeState:
    def __init__(self):
        self.not_before = {}
        self.leases = {}
        self.robots = {}
        self.deferred = []
        self.counter = 0

    def reserve(
        self,
        hostname,
        *,
        now,
        min_interval_seconds,
        lease_seconds,
    ):
        existing = self.leases.get(hostname)
        if existing and existing.lease_expires_at > now:
            raise ScopeDeferred(existing.lease_expires_at)
        due = self.not_before.get(hostname)
        if due and due > now:
            raise ScopeDeferred(due)
        self.counter += 1
        lease = HostLease(
            scope_key=hostname,
            token=f"lease-{self.counter}",
            lease_expires_at=now + timedelta(seconds=lease_seconds),
        )
        self.leases[hostname] = lease
        self.not_before[hostname] = now + timedelta(
            seconds=min_interval_seconds
        )
        return lease

    def renew(
        self,
        lease,
        *,
        lease_seconds,
        min_interval_seconds,
        now,
    ):
        current = self.leases.get(lease.scope_key)
        if current is None or current.token != lease.token:
            raise AssertionError("stale fake lease")
        due = self.not_before.get(lease.scope_key)
        if due and due > now:
            raise ScopeDeferred(due)
        renewed = HostLease(
            scope_key=lease.scope_key,
            token=lease.token,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
        )
        self.leases[lease.scope_key] = renewed
        self.not_before[lease.scope_key] = now + timedelta(
            seconds=min_interval_seconds
        )
        return renewed

    def release(self, lease):
        current = self.leases.get(lease.scope_key)
        if current and current.token == lease.token:
            del self.leases[lease.scope_key]
            return True
        return False

    def defer(self, hostname, *, not_before):
        current = self.not_before.get(hostname)
        if current is None or not_before > current:
            self.not_before[hostname] = not_before
        self.deferred.append((hostname, not_before))
        return self.not_before[hostname]

    def get_robots(self, hostname, *, now):
        cache = self.robots.get(hostname)
        if cache and cache.expires_at > now:
            return cache
        return None

    def cache_robots(
        self,
        hostname,
        *,
        status,
        body,
        checked_at,
        expires_at,
    ):
        cache = RobotsCache(
            status=status,
            body=body,
            checked_at=checked_at,
            expires_at=expires_at,
        )
        self.robots[hostname] = cache
        return cache

    def allow_robots(self, hostname, now):
        self.robots[hostname] = RobotsCache(
            status=200,
            body="User-agent: *\nAllow: /\n",
            checked_at=now,
            expires_at=now + timedelta(hours=1),
        )

    def deny_robots(self, hostname, now):
        self.robots[hostname] = RobotsCache(
            status=200,
            body="User-agent: *\nDisallow: /\n",
            checked_at=now,
            expires_at=now + timedelta(hours=1),
        )


class FakeContextSource:
    def __init__(self, context=None):
        self.context = context or HttpObservationContext()

    def get_context(self, claim):
        return self.context


def exchange(
    status,
    *,
    body=b"",
    headers=None,
    peer_ip=GLOBAL_IP,
):
    return HttpExchange(
        status=status,
        headers=headers or {},
        body=body,
        peer_ip=peer_ip,
        wire_bytes=len(body),
    )


class DirectHttpAcquisitionTests(TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.scope = FakeScopeState()
        self.scope.allow_robots("https://example.test", self.clock())
        self.policy = HttpAcquisitionPolicy(
            user_agent="Makolo Observer Test",
            host_min_interval_seconds=1.0,
            max_inline_wait_seconds=2.0,
            retry_seconds=30,
        )

    def claim(self, locator="https://example.test/resource"):
        return ObservationClaim(
            observation_ref="observer:observation:v1:test",
            claim_token="claim-token",
            worker_id="worker-a",
            leased_until=self.clock() + timedelta(minutes=5),
            target_key="web_url:v1:" + ("a" * 64),
            kind="web_url",
            locator=locator,
            source_handoff_key="observation:v1:test",
            source_handoff_generation=1,
        )

    def acquisition(
        self,
        responses,
        *,
        resolver=None,
        context=None,
        scope=None,
        policy=None,
    ):
        return DirectHttpAcquisition(
            policy=policy or self.policy,
            resolver=resolver or FakeResolver(),
            transport=FakeTransport(responses),
            scope_state=scope or self.scope,
            context_source=FakeContextSource(context),
            clock=self.clock,
            sleeper=self.clock.sleep,
        )

    def test_200_html_captures_raw_body_without_semantic_parsing(self):
        body = b"<!doctype html><html><body>Applications close Friday</body></html>"
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(
                        200,
                        body=body,
                        headers={
                            "Content-Type": "text/html; charset=utf-8",
                            "ETag": '"v1"',
                        },
                    )
                ]
            }
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(result.response_status, 200)
        self.assertEqual(result.validator_etag, '"v1"')
        self.assertEqual(len(result.artifacts), 1)
        artifact = result.artifacts[0]
        self.assertEqual(artifact.content, body)
        self.assertEqual(artifact.role, "http_response_body")
        self.assertEqual(artifact.declared_media_type, "text/html")
        self.assertEqual(artifact.detected_media_type, "text/html")
        self.assertEqual(artifact.charset, "utf-8")

    def test_404_is_observed_and_body_is_captured(self):
        body = b"<html><body>Not found</body></html>"
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(
                        404,
                        body=body,
                        headers={"Content-Type": "text/html"},
                    )
                ]
            }
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(result.response_status, 404)
        self.assertEqual(result.artifacts[0].content, body)
        self.assertIsNone(result.failure_code)

    def test_304_revalidates_without_new_artifact(self):
        context = HttpObservationContext(
            etag='"old"',
            last_modified="Sat, 19 Sep 2026 10:00:00 GMT",
            validator_artifact_ref="observer:artifact:v1:old",
        )
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(
                        304,
                        headers={"ETag": '"new"'},
                    )
                ]
            },
            context=context,
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(
            result.outcome,
            ObservationOutcome.NOT_MODIFIED,
        )
        self.assertEqual(result.artifacts, ())
        self.assertEqual(
            result.revalidated_artifact_ref,
            "observer:artifact:v1:old",
        )
        self.assertEqual(result.validator_etag, '"new"')
        call = acquisition.transport.calls[0]
        self.assertEqual(call["headers"]["If-None-Match"], '"old"')
        self.assertEqual(
            call["headers"]["If-Modified-Since"],
            "Sat, 19 Sep 2026 10:00:00 GMT",
        )

    def test_conditional_headers_are_not_forwarded_after_redirect(self):
        context = HttpObservationContext(
            etag='"old"',
            last_modified="Sat, 19 Sep 2026 10:00:00 GMT",
        )
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(302, headers={"Location": "/final"})
                ],
                "https://example.test/final": [
                    exchange(200, body=b"ok")
                ],
            },
            context=context,
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(result.redirect_count, 1)
        self.assertIn(
            "If-None-Match",
            acquisition.transport.calls[0]["headers"],
        )
        self.assertNotIn(
            "If-None-Match",
            acquisition.transport.calls[1]["headers"],
        )
        self.assertNotIn(
            "If-Modified-Since",
            acquisition.transport.calls[1]["headers"],
        )
        self.assertEqual(self.clock.now.second, 1)

    def test_redirect_loop_fails_without_unbounded_requests(self):
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(302, headers={"Location": "/next"})
                ],
                "https://example.test/next": [
                    exchange(302, headers={"Location": "/resource"})
                ],
            }
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(result.failure_code, "http.redirect_loop")
        self.assertIsNone(result.retry_at)
        self.assertEqual(len(acquisition.transport.calls), 2)

    def test_redirect_limit_is_per_chain_not_shared_with_cached_robots(self):
        policy = HttpAcquisitionPolicy(
            user_agent="Makolo Observer Test",
            host_min_interval_seconds=0,
            max_redirects=1,
        )
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(302, headers={"Location": "/final"})
                ],
                "https://example.test/final": [
                    exchange(200, body=b"ok")
                ],
            },
            policy=policy,
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(result.redirect_count, 1)

    def test_mixed_dns_answer_is_rejected_before_transport(self):
        resolver = FakeResolver(
            {"example.test": [[GLOBAL_IP, "10.0.0.1"]]}
        )
        acquisition = self.acquisition(
            {"https://example.test/resource": [exchange(200)]},
            resolver=resolver,
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(
            result.failure_code,
            "security.non_global_address",
        )
        self.assertEqual(acquisition.transport.calls, [])

    def test_dns_is_revalidated_on_every_redirect_connection(self):
        resolver = FakeResolver(
            {
                "example.test": [
                    [GLOBAL_IP],
                    ["10.0.0.2"],
                ]
            }
        )
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(302, headers={"Location": "/next"})
                ],
                "https://example.test/next": [exchange(200)],
            },
            resolver=resolver,
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(
            result.failure_code,
            "security.non_global_address",
        )
        self.assertEqual(resolver.calls.count("example.test"), 2)
        self.assertEqual(len(acquisition.transport.calls), 1)

    def test_private_literal_and_cloud_metadata_addresses_are_rejected(self):
        for locator in (
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/",
        ):
            with self.subTest(locator=locator):
                acquisition = self.acquisition({})
                result = acquisition.acquire(self.claim(locator))
                self.assertEqual(
                    result.outcome,
                    ObservationOutcome.FAILED,
                )
                self.assertIn(
                    result.failure_code,
                    {
                        "security.localhost",
                        "security.non_global_address",
                    },
                )

    def test_localhost_is_rejected_before_dns(self):
        resolver = FakeResolver()
        acquisition = self.acquisition({}, resolver=resolver)

        result = acquisition.acquire(
            self.claim("http://localhost/internal")
        )

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(result.failure_code, "security.localhost")
        self.assertEqual(resolver.calls, [])

    def test_actual_peer_must_equal_selected_validated_ip(self):
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(200, peer_ip=OTHER_GLOBAL_IP)
                ]
            }
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(result.failure_code, "security.peer_mismatch")

    def test_non_allowed_port_is_rejected_before_transport(self):
        acquisition = self.acquisition({})

        result = acquisition.acquire(
            self.claim("https://example.test:8443/resource")
        )

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(
            result.failure_code,
            "security.port_not_allowed",
        )
        self.assertEqual(acquisition.transport.calls, [])

    def test_https_to_http_redirect_is_rejected_by_default(self):
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(
                        302,
                        headers={
                            "Location": "http://example.test/insecure"
                        },
                    )
                ]
            }
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(
            result.failure_code,
            "security.redirect_downgrade",
        )

    def test_redirect_destination_robots_is_checked_before_fetch(self):
        self.scope.deny_robots("https://other.test", self.clock())
        resolver = FakeResolver(
            {
                "example.test": [[GLOBAL_IP]],
                "other.test": [[OTHER_GLOBAL_IP]],
            }
        )
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(
                        302,
                        headers={
                            "Location": "https://other.test/private"
                        },
                    )
                ],
                "https://other.test/private": [
                    exchange(200, peer_ip=OTHER_GLOBAL_IP)
                ],
            },
            resolver=resolver,
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(result.failure_code, "robots.disallowed")
        self.assertEqual(len(acquisition.transport.calls), 1)

    def test_robots_disallow_stops_target_request(self):
        scope = FakeScopeState()
        acquisition = self.acquisition(
            {
                "https://example.test/robots.txt": [
                    exchange(
                        200,
                        body=(
                            b"User-agent: MakoloObserver\n"
                            b"Disallow: /private\n"
                        ),
                        headers={"Content-Type": "text/plain"},
                    )
                ]
            },
            scope=scope,
        )

        result = acquisition.acquire(
            self.claim("https://example.test/private")
        )

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(result.failure_code, "robots.disallowed")
        self.assertEqual(len(acquisition.transport.calls), 1)
        self.assertIsNotNone(result.retry_at)

    def test_robots_503_defers_without_fetching_target(self):
        scope = FakeScopeState()
        acquisition = self.acquisition(
            {
                "https://example.test/robots.txt": [
                    exchange(
                        503,
                        headers={"Retry-After": "120"},
                    )
                ]
            },
            scope=scope,
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(result.failure_code, "robots.unavailable")
        self.assertEqual(
            result.retry_at,
            self.clock() + timedelta(seconds=120),
        )
        self.assertEqual(len(acquisition.transport.calls), 1)
        self.assertTrue(scope.deferred)

    def test_large_crawl_delay_defers_target_instead_of_sleeping_unbounded(self):
        scope = FakeScopeState()
        acquisition = self.acquisition(
            {
                "https://example.test/robots.txt": [
                    exchange(
                        200,
                        body=(
                            b"User-agent: MakoloObserver\n"
                            b"Allow: /\n"
                            b"Crawl-delay: 10\n"
                        ),
                    )
                ]
            },
            scope=scope,
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(result.failure_code, "politeness.not_before")
        self.assertEqual(
            result.retry_at,
            self.clock() + timedelta(seconds=10),
        )
        self.assertEqual(len(acquisition.transport.calls), 1)

    def test_429_respects_retry_after_and_defers_host(self):
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(
                        429,
                        headers={"Retry-After": "90"},
                    )
                ]
            }
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(result.failure_code, "http.rate_limited")
        self.assertEqual(
            result.retry_at,
            self.clock() + timedelta(seconds=90),
        )
        self.assertTrue(self.scope.deferred)

    def test_gzip_body_is_bounded_after_decompression(self):
        payload = b"A" * 100
        compressed = gzip.compress(payload)
        policy = HttpAcquisitionPolicy(
            user_agent="Makolo Observer Test",
            host_min_interval_seconds=0,
            max_decoded_bytes=32,
        )
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(
                        200,
                        body=compressed,
                        headers={"Content-Encoding": "gzip"},
                    )
                ]
            },
            policy=policy,
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(
            result.failure_code,
            "http.decoded_too_large",
        )
        self.assertEqual(result.artifacts, ())

    def test_unsupported_content_encoding_is_terminal(self):
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(
                        200,
                        body=b"opaque",
                        headers={"Content-Encoding": "br"},
                    )
                ]
            }
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(
            result.failure_code,
            "http.unsupported_content_encoding",
        )
        self.assertIsNone(result.retry_at)

    def test_transport_size_limit_failure_is_terminal(self):
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    HttpTransportFailure("http.response_too_large")
                ]
            }
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(
            result.failure_code,
            "http.response_too_large",
        )
        self.assertIsNone(result.retry_at)

    def test_transport_timeout_is_retryable(self):
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    HttpTransportFailure("http.timeout")
                ]
            }
        )

        result = acquisition.acquire(self.claim())

        self.assertEqual(result.outcome, ObservationOutcome.FAILED)
        self.assertEqual(result.failure_code, "http.timeout")
        self.assertEqual(
            result.retry_at,
            self.clock() + timedelta(seconds=30),
        )

    def test_no_credentials_or_cookies_are_sent(self):
        acquisition = self.acquisition(
            {
                "https://example.test/resource": [
                    exchange(200)
                ]
            }
        )

        acquisition.acquire(self.claim())

        headers = acquisition.transport.calls[0]["headers"]
        lowered = {key.lower() for key in headers}
        self.assertNotIn("authorization", lowered)
        self.assertNotIn("cookie", lowered)
        self.assertNotIn("proxy-authorization", lowered)
