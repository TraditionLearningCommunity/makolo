from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from .errors import ObserverContractError


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ObserverContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ObserverContractError(f"{name} must not be empty")
    return value


def _positive_number(name: str, value, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObserverContractError(f"{name} must be numeric")
    value = float(value)
    if value < 0 or (not allow_zero and value == 0):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ObserverContractError(f"{name} must be {qualifier}")
    return value


def _positive_int(name: str, value: int, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ObserverContractError(f"{name} must be an integer")
    if value < 0 or (not allow_zero and value == 0):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ObserverContractError(f"{name} must be {qualifier}")
    return value


def _aware(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ObserverContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ObserverContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class HttpAcquisitionPolicy:
    """Safety and politeness policy for public direct-HTTP observation.

    Defaults are bounded safety defaults, not production SLAs.
    """

    user_agent: str = "MakoloObserver/1.0"
    robots_user_agent: str = "MakoloObserver"
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 20.0
    max_redirects: int = 5
    max_wire_bytes: int = 8 * 1024 * 1024
    max_decoded_bytes: int = 16 * 1024 * 1024
    robots_max_bytes: int = 256 * 1024
    robots_cache_seconds: int = 3600
    host_min_interval_seconds: float = 1.0
    max_inline_wait_seconds: float = 2.0
    host_lease_seconds: int = 120
    retry_seconds: int = 60
    allow_https_to_http_redirect: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "user_agent",
            _required_text("user_agent", self.user_agent),
        )
        object.__setattr__(
            self,
            "robots_user_agent",
            _required_text(
                "robots_user_agent",
                self.robots_user_agent,
            ),
        )
        object.__setattr__(
            self,
            "connect_timeout_seconds",
            _positive_number(
                "connect_timeout_seconds",
                self.connect_timeout_seconds,
            ),
        )
        object.__setattr__(
            self,
            "read_timeout_seconds",
            _positive_number(
                "read_timeout_seconds",
                self.read_timeout_seconds,
            ),
        )
        object.__setattr__(
            self,
            "host_min_interval_seconds",
            _positive_number(
                "host_min_interval_seconds",
                self.host_min_interval_seconds,
                allow_zero=True,
            ),
        )
        object.__setattr__(
            self,
            "max_inline_wait_seconds",
            _positive_number(
                "max_inline_wait_seconds",
                self.max_inline_wait_seconds,
                allow_zero=True,
            ),
        )
        for name in (
            "max_redirects",
            "max_wire_bytes",
            "max_decoded_bytes",
            "robots_max_bytes",
            "robots_cache_seconds",
            "host_lease_seconds",
            "retry_seconds",
        ):
            object.__setattr__(
                self,
                name,
                _positive_int(name, getattr(self, name), allow_zero=(name == "max_redirects")),
            )
        if not isinstance(self.allow_https_to_http_redirect, bool):
            raise ObserverContractError(
                "allow_https_to_http_redirect must be boolean"
            )
        if self.robots_max_bytes > self.max_wire_bytes:
            raise ObserverContractError(
                "robots_max_bytes must not exceed max_wire_bytes"
            )

    @property
    def profile_fingerprint(self) -> str:
        payload = {
            "version": 1,
            "mode": "public-http",
            "user_agent": self.user_agent,
            "accept": "*/*",
            "credentials": "none",
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "public-http:v1:" + hashlib.sha256(encoded).hexdigest()

    @property
    def policy_fingerprint(self) -> str:
        payload = {
            "version": 1,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "read_timeout_seconds": self.read_timeout_seconds,
            "max_redirects": self.max_redirects,
            "max_wire_bytes": self.max_wire_bytes,
            "max_decoded_bytes": self.max_decoded_bytes,
            "robots_max_bytes": self.robots_max_bytes,
            "robots_cache_seconds": self.robots_cache_seconds,
            "host_min_interval_seconds": self.host_min_interval_seconds,
            "max_inline_wait_seconds": self.max_inline_wait_seconds,
            "host_lease_seconds": self.host_lease_seconds,
            "retry_seconds": self.retry_seconds,
            "allow_https_to_http_redirect": self.allow_https_to_http_redirect,
            "robots_user_agent": self.robots_user_agent,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "observer-http:v1:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class HttpExchange:
    status: int
    headers: Mapping[str, str]
    body: bytes
    peer_ip: str
    wire_bytes: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.status, int)
            or isinstance(self.status, bool)
            or not 100 <= self.status <= 599
        ):
            raise ObserverContractError(
                "HTTP exchange status must be valid"
            )
        if not isinstance(self.body, bytes):
            raise ObserverContractError(
                "HTTP exchange body must be bytes"
            )
        object.__setattr__(
            self,
            "peer_ip",
            _required_text("peer_ip", self.peer_ip),
        )
        object.__setattr__(
            self,
            "wire_bytes",
            _positive_int(
                "wire_bytes",
                self.wire_bytes,
                allow_zero=True,
            ),
        )
        if self.wire_bytes != len(self.body):
            raise ObserverContractError(
                "wire_bytes must match the captured HTTP body length"
            )
        normalized = {}
        if not isinstance(self.headers, Mapping):
            raise ObserverContractError(
                "HTTP exchange headers must be a mapping"
            )
        for key, value in self.headers.items():
            name = _required_text("header name", str(key)).lower()
            normalized[name] = str(value).strip()
        object.__setattr__(
            self,
            "headers",
            MappingProxyType(normalized),
        )


@dataclass(frozen=True, slots=True)
class HttpObservationContext:
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    validator_artifact_ref: Optional[str] = None


@dataclass(frozen=True, slots=True)
class HostLease:
    scope_key: str
    token: str
    lease_expires_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scope_key",
            _required_text("scope_key", self.scope_key),
        )
        object.__setattr__(
            self,
            "token",
            _required_text("token", self.token),
        )
        object.__setattr__(
            self,
            "lease_expires_at",
            _aware("lease_expires_at", self.lease_expires_at),
        )


@dataclass(frozen=True, slots=True)
class RobotsCache:
    status: int
    body: str
    checked_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.status, int)
            or isinstance(self.status, bool)
            or not 100 <= self.status <= 599
        ):
            raise ObserverContractError(
                "robots status must be a valid HTTP status"
            )
        if not isinstance(self.body, str):
            raise ObserverContractError("robots body must be text")
        object.__setattr__(
            self,
            "checked_at",
            _aware("checked_at", self.checked_at),
        )
        object.__setattr__(
            self,
            "expires_at",
            _aware("expires_at", self.expires_at),
        )
        if self.expires_at <= self.checked_at:
            raise ObserverContractError(
                "robots cache expiry must follow checked_at"
            )


class HttpTransportFailure(Exception):
    def __init__(self, code: str) -> None:
        self.code = _required_text("code", code)
        super().__init__(self.code)


class ScopeDeferred(Exception):
    def __init__(self, retry_at: datetime) -> None:
        self.retry_at = _aware("retry_at", retry_at)
        super().__init__("HTTP scope is not yet eligible")


class NetworkSafetyFailure(Exception):
    def __init__(self, code: str) -> None:
        self.code = _required_text("code", code)
        super().__init__(self.code)
