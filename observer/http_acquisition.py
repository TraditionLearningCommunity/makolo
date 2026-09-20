from __future__ import annotations

import gzip
import io
import ipaddress
import time
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import Message
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from .contracts import AttemptStrategy, ObservationOutcome
from .http_contracts import (
    HttpAcquisitionPolicy,
    HttpObservationContext,
    HttpTransportFailure,
    NetworkSafetyFailure,
    RobotsCache,
    ScopeDeferred,
)
from .runtime_contracts import (
    AcquiredArtifact,
    AcquisitionResult,
    ObservationClaim,
)


REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
RETRYABLE_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
TRANSIENT_TRANSPORT_FAILURES = frozenset(
    {
        "security.dns_unresolved",
        "http.timeout",
        "http.network_error",
    }
)


@dataclass
class _Stats:
    wire_bytes: int = 0
    decoded_bytes: int = 0
    redirect_count: int = 0
    final_locator: str | None = None
    response_status: int | None = None


class _ExpectedFailure(Exception):
    def __init__(
        self,
        code: str,
        *,
        retry_at: datetime | None = None,
        response_status: int | None = None,
    ) -> None:
        self.code = code
        self.retry_at = retry_at
        self.response_status = response_status
        super().__init__(code)


def _utc_now(clock) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("HTTP acquisition clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def _render_host(hostname: str) -> str:
    return f"[{hostname}]" if ":" in hostname else hostname


def _normalize_http_url(value: str) -> str:
    if not isinstance(value, str):
        raise NetworkSafetyFailure("security.malformed_locator")
    value = value.strip()
    if not value or any(char.isspace() for char in value):
        raise NetworkSafetyFailure("security.malformed_locator")
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise NetworkSafetyFailure(
            "security.malformed_locator"
        ) from exc
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not hostname:
        raise NetworkSafetyFailure("security.unsupported_locator")
    if parts.username is not None or parts.password is not None:
        raise NetworkSafetyFailure("security.embedded_credentials")

    raw_host = hostname.rstrip(".")
    if not raw_host:
        raise NetworkSafetyFailure("security.malformed_locator")
    try:
        canonical_host = ipaddress.ip_address(raw_host).compressed.lower()
    except ValueError:
        try:
            canonical_host = raw_host.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise NetworkSafetyFailure(
                "security.malformed_locator"
            ) from exc

    if (
        canonical_host == "localhost"
        or canonical_host.endswith(".localhost")
    ):
        raise NetworkSafetyFailure("security.localhost")

    default_port = 443 if scheme == "https" else 80
    netloc = _render_host(canonical_host)
    if port not in {None, default_port}:
        netloc = f"{netloc}:{port}"
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return parts.scheme, parts.hostname or "", port


def _parse_retry_after(
    value: str | None,
    *,
    now: datetime,
    fallback_seconds: int,
) -> datetime:
    fallback = now + timedelta(seconds=fallback_seconds)
    if not value:
        return fallback
    raw = value.strip()
    if not raw:
        return fallback
    try:
        seconds = int(raw)
    except ValueError:
        seconds = None
    if seconds is not None:
        if seconds < 0:
            return fallback
        return now + timedelta(seconds=seconds)
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        return fallback
    if parsed is None:
        return fallback
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return parsed if parsed > now else fallback


def _content_type(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    message = Message()
    message["content-type"] = value
    media_type = message.get_content_type().lower()
    charset = message.get_content_charset()
    return media_type or None, charset or None


def _detected_media_type(payload: bytes) -> str | None:
    prefix = payload[:1024].lstrip()
    lowered = prefix.lower()
    if prefix.startswith(b"%PDF-"):
        return "application/pdf"
    if (
        lowered.startswith(b"<!doctype html")
        or lowered.startswith(b"<html")
        or lowered.startswith(b"<head")
        or lowered.startswith(b"<body")
    ):
        return "text/html"
    if (
        lowered.startswith(b"<?xml")
        or lowered.startswith(b"<rss")
        or lowered.startswith(b"<feed")
    ):
        return "application/xml"
    return None


def _decode_http_body(
    raw: bytes,
    *,
    content_encoding: str | None,
    max_decoded_bytes: int,
) -> bytes:
    encoding = (content_encoding or "").strip().lower()
    if not encoding or encoding == "identity":
        if len(raw) > max_decoded_bytes:
            raise _ExpectedFailure("http.decoded_too_large")
        return raw
    if "," in encoding:
        raise _ExpectedFailure("http.unsupported_content_encoding")
    try:
        if encoding in {"gzip", "x-gzip"}:
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as handle:
                decoded = handle.read(max_decoded_bytes + 1)
        elif encoding == "deflate":
            inflater = zlib.decompressobj()
            decoded = inflater.decompress(raw, max_decoded_bytes + 1)
            if inflater.unconsumed_tail:
                raise _ExpectedFailure("http.decoded_too_large")
            remaining = max_decoded_bytes - len(decoded) + 1
            if remaining > 0:
                decoded += inflater.flush(remaining)
        else:
            raise _ExpectedFailure(
                "http.unsupported_content_encoding"
            )
    except _ExpectedFailure:
        raise
    except (OSError, EOFError, zlib.error) as exc:
        raise _ExpectedFailure(
            "http.invalid_content_encoding"
        ) from exc
    if len(decoded) > max_decoded_bytes:
        raise _ExpectedFailure("http.decoded_too_large")
    return decoded


class DirectHttpAcquisition:
    """Public direct-HTTP acquisition without semantic interpretation."""

    strategy = AttemptStrategy.DIRECT_HTTP

    def __init__(
        self,
        *,
        policy: HttpAcquisitionPolicy,
        resolver,
        transport,
        scope_state,
        context_source,
        clock,
        sleeper=None,
    ) -> None:
        self.policy = policy
        self.resolver = resolver
        self.transport = transport
        self.scope_state = scope_state
        self.context_source = context_source
        self.clock = clock
        self.sleeper = sleeper or time.sleep

    def _failure(
        self,
        *,
        code: str,
        now: datetime,
        stats: _Stats,
        retry_at: datetime | None = None,
        response_status: int | None = None,
    ) -> AcquisitionResult:
        return AcquisitionResult(
            outcome=ObservationOutcome.FAILED,
            observed_at=now,
            final_locator=stats.final_locator,
            response_status=(
                response_status
                if response_status is not None
                else stats.response_status
            ),
            failure_code=code,
            retry_at=retry_at,
            redirect_count=stats.redirect_count,
            wire_bytes=stats.wire_bytes,
            decoded_bytes=stats.decoded_bytes,
        )

    def _resolve_public_addresses(self, hostname: str) -> tuple[str, ...]:
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            literal = None
        if literal is not None:
            addresses = (literal.compressed,)
        else:
            addresses = tuple(self.resolver.resolve(hostname))
        if not addresses:
            raise _ExpectedFailure("security.dns_unresolved")

        normalized = []
        for value in addresses:
            try:
                address = ipaddress.ip_address(value)
            except ValueError as exc:
                raise NetworkSafetyFailure(
                    "security.invalid_dns_answer"
                ) from exc
            if not address.is_global:
                raise NetworkSafetyFailure(
                    "security.non_global_address"
                )
            rendered = address.compressed
            if rendered not in normalized:
                normalized.append(rendered)
        return tuple(normalized)

    def _lease_for(
        self,
        hostname: str,
        *,
        active_leases: dict[str, object],
        now: datetime,
    ):
        lease = active_leases.get(hostname)
        if lease is not None:
            try:
                lease = self.scope_state.renew(
                    lease,
                    lease_seconds=self.policy.host_lease_seconds,
                    min_interval_seconds=(
                        self.policy.host_min_interval_seconds
                    ),
                    now=now,
                )
            except ScopeDeferred as exc:
                wait_seconds = max(
                    0.0,
                    (exc.retry_at - now).total_seconds(),
                )
                if wait_seconds > self.policy.max_inline_wait_seconds:
                    raise
                self.sleeper(wait_seconds)
                now = _utc_now(self.clock)
                lease = self.scope_state.renew(
                    lease,
                    lease_seconds=self.policy.host_lease_seconds,
                    min_interval_seconds=(
                        self.policy.host_min_interval_seconds
                    ),
                    now=now,
                )
            active_leases[hostname] = lease
            return lease
        lease = self.scope_state.reserve(
            hostname,
            now=now,
            min_interval_seconds=self.policy.host_min_interval_seconds,
            lease_seconds=self.policy.host_lease_seconds,
        )
        active_leases[hostname] = lease
        return lease

    def _exchange(
        self,
        url: str,
        *,
        headers: dict[str, str],
        max_wire_bytes: int,
        active_leases: dict[str, object],
        stats: _Stats,
    ):
        url = _normalize_http_url(url)
        parts = urlsplit(url)
        hostname = parts.hostname or ""
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if port not in self.policy.allowed_ports:
            raise NetworkSafetyFailure("security.port_not_allowed")
        now = _utc_now(self.clock)
        self._lease_for(
            hostname,
            active_leases=active_leases,
            now=now,
        )
        addresses = self._resolve_public_addresses(hostname)
        selected = addresses[0]
        try:
            exchange = self.transport.request(
                url=url,
                connect_ip=selected,
                headers=headers,
                connect_timeout_seconds=(
                    self.policy.connect_timeout_seconds
                ),
                read_timeout_seconds=self.policy.read_timeout_seconds,
                max_wire_bytes=max_wire_bytes,
            )
        except HttpTransportFailure as exc:
            retry_at = None
            if exc.code in TRANSIENT_TRANSPORT_FAILURES:
                retry_at = now + timedelta(
                    seconds=self.policy.retry_seconds
                )
            raise _ExpectedFailure(
                exc.code,
                retry_at=retry_at,
            ) from exc

        try:
            peer = ipaddress.ip_address(exchange.peer_ip)
        except ValueError as exc:
            raise NetworkSafetyFailure(
                "security.invalid_peer_address"
            ) from exc
        if not peer.is_global or peer.compressed != selected:
            raise NetworkSafetyFailure("security.peer_mismatch")

        stats.wire_bytes += exchange.wire_bytes
        stats.response_status = exchange.status
        return url, exchange

    def _follow(
        self,
        start_url: str,
        *,
        initial_headers: dict[str, str],
        max_wire_bytes: int,
        active_leases: dict[str, object],
        stats: _Stats,
        redirect_guard=None,
    ):
        current = _normalize_http_url(start_url)
        visited = {current}
        first_request = True
        chain_redirects = 0

        while True:
            headers = dict(
                initial_headers
                if first_request
                else self._base_headers()
            )
            current, exchange = self._exchange(
                current,
                headers=headers,
                max_wire_bytes=max_wire_bytes,
                active_leases=active_leases,
                stats=stats,
            )
            stats.final_locator = current
            if exchange.status not in REDIRECT_STATUSES:
                return current, exchange

            location = exchange.headers.get("location")
            if not location:
                return current, exchange
            if chain_redirects >= self.policy.max_redirects:
                raise _ExpectedFailure(
                    "http.redirect_limit",
                    response_status=exchange.status,
                )

            next_url = _normalize_http_url(urljoin(current, location))
            if next_url in visited:
                raise _ExpectedFailure(
                    "http.redirect_loop",
                    response_status=exchange.status,
                )
            if (
                _origin(current)[0] == "https"
                and _origin(next_url)[0] == "http"
                and not self.policy.allow_https_to_http_redirect
            ):
                raise NetworkSafetyFailure(
                    "security.redirect_downgrade"
                )

            if redirect_guard is not None:
                redirect_guard(next_url)

            chain_redirects += 1
            stats.redirect_count += 1
            visited.add(next_url)
            current = next_url
            first_request = False

    def _base_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.policy.user_agent,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }

    def _robots_scope_key(self, target_url: str) -> str:
        parts = urlsplit(target_url)
        return urlunsplit(
            (parts.scheme, parts.netloc, "", "", "")
        ).lower()

    def _robots_url(self, target_url: str) -> str:
        parts = urlsplit(target_url)
        return urlunsplit(
            (parts.scheme, parts.netloc, "/robots.txt", "", "")
        )

    def _robots_cache(
        self,
        target_url: str,
        *,
        active_leases: dict[str, object],
        stats: _Stats,
    ) -> tuple[RobotsCache, bool]:
        hostname = urlsplit(target_url).hostname or ""
        origin_key = self._robots_scope_key(target_url)
        now = _utc_now(self.clock)
        cached = self.scope_state.get_robots(origin_key, now=now)
        if cached is not None:
            return cached, False

        robots_url = self._robots_url(target_url)
        robots_stats = _Stats(final_locator=robots_url)
        _final, exchange = self._follow(
            robots_url,
            initial_headers=self._base_headers(),
            max_wire_bytes=self.policy.robots_max_bytes,
            active_leases=active_leases,
            stats=robots_stats,
        )
        stats.wire_bytes += robots_stats.wire_bytes
        stats.decoded_bytes += robots_stats.decoded_bytes
        stats.redirect_count += robots_stats.redirect_count
        now = _utc_now(self.clock)
        status = exchange.status
        if status == 429 or status >= 500:
            retry_at = _parse_retry_after(
                exchange.headers.get("retry-after"),
                now=now,
                fallback_seconds=self.policy.retry_seconds,
            )
            self.scope_state.defer(hostname, not_before=retry_at)
            raise _ExpectedFailure(
                "robots.unavailable",
                retry_at=retry_at,
                response_status=status,
            )

        body = ""
        if 200 <= status < 300:
            decoded = _decode_http_body(
                exchange.body,
                content_encoding=exchange.headers.get(
                    "content-encoding"
                ),
                max_decoded_bytes=self.policy.robots_max_bytes,
            )
            robots_stats.decoded_bytes += len(decoded)
            stats.decoded_bytes += len(decoded)
            body = decoded.decode("utf-8", errors="replace")

        cache = self.scope_state.cache_robots(
            origin_key,
            status=status,
            body=body,
            checked_at=now,
            expires_at=now
            + timedelta(seconds=self.policy.robots_cache_seconds),
        )
        return cache, True

    def _robots_allows(
        self,
        target_url: str,
        *,
        cache: RobotsCache,
    ) -> tuple[bool, float]:
        if cache.status in {401, 403}:
            return False, 0.0
        if cache.status >= 400:
            return True, 0.0

        parser = RobotFileParser()
        parser.set_url(self._robots_url(target_url))
        parser.parse(cache.body.splitlines())
        allowed = parser.can_fetch(
            self.policy.robots_user_agent,
            target_url,
        )
        delay = parser.crawl_delay(self.policy.robots_user_agent) or 0
        rate = parser.request_rate(self.policy.robots_user_agent)
        if rate is not None and rate.requests > 0:
            delay = max(delay, rate.seconds / rate.requests)
        return allowed, float(delay)

    def _ensure_robots(
        self,
        target_url: str,
        *,
        active_leases: dict[str, object],
        stats: _Stats,
    ) -> None:
        if (urlsplit(target_url).path or "/") == "/robots.txt":
            return
        cache, fetched = self._robots_cache(
            target_url,
            active_leases=active_leases,
            stats=stats,
        )
        allowed, crawl_delay = self._robots_allows(
            target_url,
            cache=cache,
        )
        hostname = urlsplit(target_url).hostname or ""
        if fetched and crawl_delay > 0:
            self.scope_state.defer(
                hostname,
                not_before=_utc_now(self.clock)
                + timedelta(seconds=crawl_delay),
            )
        if not allowed:
            raise _ExpectedFailure(
                "robots.disallowed",
                retry_at=cache.expires_at,
            )

    def _target_headers(
        self,
        context: HttpObservationContext,
    ) -> dict[str, str]:
        headers = self._base_headers()
        if context.etag:
            headers["If-None-Match"] = context.etag
        if context.last_modified:
            headers["If-Modified-Since"] = context.last_modified
        return headers

    def acquire(self, claim: ObservationClaim) -> AcquisitionResult:
        now = _utc_now(self.clock)
        stats = _Stats(final_locator=claim.locator)
        active_leases: dict[str, object] = {}
        try:
            if claim.kind != "web_url":
                return self._failure(
                    code="http.unsupported_target_kind",
                    now=now,
                    stats=stats,
                )
            target_url = _normalize_http_url(claim.locator)
            stats.final_locator = target_url
            context = self.context_source.get_context(claim)

            self._ensure_robots(
                target_url,
                active_leases=active_leases,
                stats=stats,
            )

            final_url, exchange = self._follow(
                target_url,
                initial_headers=self._target_headers(context),
                max_wire_bytes=self.policy.max_wire_bytes,
                active_leases=active_leases,
                stats=stats,
                redirect_guard=lambda next_url: self._ensure_robots(
                    next_url,
                    active_leases=active_leases,
                    stats=stats,
                ),
            )
            stats.final_locator = final_url
            now = _utc_now(self.clock)
            status = exchange.status

            if status == 304:
                return AcquisitionResult(
                    outcome=ObservationOutcome.NOT_MODIFIED,
                    observed_at=now,
                    final_locator=final_url,
                    response_status=status,
                    revalidated_artifact_ref=(
                        context.validator_artifact_ref
                    ),
                    validator_etag=(
                        exchange.headers.get("etag") or context.etag
                    ),
                    validator_last_modified=(
                        exchange.headers.get("last-modified")
                        or context.last_modified
                    ),
                    redirect_count=stats.redirect_count,
                    wire_bytes=stats.wire_bytes,
                    decoded_bytes=stats.decoded_bytes,
                )

            if status in RETRYABLE_HTTP_STATUSES or status >= 500:
                retry_at = _parse_retry_after(
                    exchange.headers.get("retry-after"),
                    now=now,
                    fallback_seconds=self.policy.retry_seconds,
                )
                hostname = urlsplit(final_url).hostname or ""
                if status in {429, 503}:
                    self.scope_state.defer(
                        hostname,
                        not_before=retry_at,
                    )
                return self._failure(
                    code=(
                        "http.rate_limited"
                        if status == 429
                        else "http.server_error"
                        if status >= 500
                        else "http.retryable_status"
                    ),
                    now=now,
                    stats=stats,
                    retry_at=retry_at,
                    response_status=status,
                )

            decoded = _decode_http_body(
                exchange.body,
                content_encoding=exchange.headers.get(
                    "content-encoding"
                ),
                max_decoded_bytes=self.policy.max_decoded_bytes,
            )
            stats.decoded_bytes += len(decoded)
            media_type, charset = _content_type(
                exchange.headers.get("content-type")
            )
            artifacts = ()
            if decoded:
                artifacts = (
                    AcquiredArtifact(
                        content=decoded,
                        role="http_response_body",
                        captured_at=now,
                        declared_media_type=media_type,
                        detected_media_type=_detected_media_type(decoded),
                        charset=charset,
                    ),
                )

            return AcquisitionResult(
                outcome=ObservationOutcome.OBSERVED,
                observed_at=now,
                final_locator=final_url,
                response_status=status,
                artifacts=artifacts,
                validator_etag=exchange.headers.get("etag"),
                validator_last_modified=exchange.headers.get(
                    "last-modified"
                ),
                redirect_count=stats.redirect_count,
                wire_bytes=stats.wire_bytes,
                decoded_bytes=stats.decoded_bytes,
            )
        except ScopeDeferred as exc:
            return self._failure(
                code="politeness.not_before",
                now=_utc_now(self.clock),
                stats=stats,
                retry_at=exc.retry_at,
            )
        except NetworkSafetyFailure as exc:
            return self._failure(
                code=exc.code,
                now=_utc_now(self.clock),
                stats=stats,
            )
        except _ExpectedFailure as exc:
            return self._failure(
                code=exc.code,
                now=_utc_now(self.clock),
                stats=stats,
                retry_at=exc.retry_at,
                response_status=exc.response_status,
            )
        finally:
            for lease in tuple(active_leases.values()):
                self.scope_state.release(lease)
