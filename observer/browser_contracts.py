from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from importlib import metadata
from types import MappingProxyType
from typing import Callable, Mapping, Optional, Tuple

from .errors import ObserverContractError
from .http_contracts import HttpAcquisitionPolicy, SafeHttpResourceResult


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ObserverContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ObserverContractError(f"{name} must not be empty")
    return value


def _positive_int(name: str, value: int, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ObserverContractError(f"{name} must be an integer")
    if value < 0 or (not allow_zero and value == 0):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ObserverContractError(f"{name} must be {qualifier}")
    return value


def _playwright_version() -> str:
    try:
        return metadata.version("playwright")
    except metadata.PackageNotFoundError:
        return "unavailable"


@dataclass(frozen=True, slots=True)
class BrowserAcquisitionPolicy:
    http_policy: HttpAcquisitionPolicy
    engine: str = "chromium"
    playwright_version: str = field(default_factory=_playwright_version)
    locale: str = "en-US"
    viewport_width: int = 1280
    viewport_height: int = 720
    settle_timeout_seconds: int = 5
    max_requests: int = 64
    max_total_wire_bytes: int = 24 * 1024 * 1024
    max_total_decoded_bytes: int = 32 * 1024 * 1024
    max_rendered_dom_bytes: int = 4 * 1024 * 1024
    blocked_resource_types: Tuple[str, ...] = (
        "font",
        "image",
        "media",
    )
    sink_proxy: str = "http://127.0.0.1:9"

    def __post_init__(self) -> None:
        if not isinstance(self.http_policy, HttpAcquisitionPolicy):
            raise ObserverContractError(
                "http_policy must be HttpAcquisitionPolicy"
            )
        engine = _required_text("engine", self.engine).lower()
        if engine != "chromium":
            raise ObserverContractError(
                "Lot 4 supports only the audited chromium engine"
            )
        object.__setattr__(self, "engine", engine)
        object.__setattr__(
            self,
            "playwright_version",
            _required_text(
                "playwright_version",
                self.playwright_version,
            ),
        )
        if self.playwright_version == "unavailable":
            raise ObserverContractError(
                "Playwright Python package is required for browser acquisition"
            )
        object.__setattr__(
            self,
            "locale",
            _required_text("locale", self.locale),
        )
        object.__setattr__(
            self,
            "sink_proxy",
            _required_text("sink_proxy", self.sink_proxy),
        )
        for name in (
            "viewport_width",
            "viewport_height",
            "settle_timeout_seconds",
            "max_requests",
            "max_total_wire_bytes",
            "max_total_decoded_bytes",
            "max_rendered_dom_bytes",
        ):
            object.__setattr__(
                self,
                name,
                _positive_int(name, getattr(self, name)),
            )
        resource_types = tuple(
            dict.fromkeys(
                _required_text("blocked_resource_type", item).lower()
                for item in self.blocked_resource_types
            )
        )
        object.__setattr__(
            self,
            "blocked_resource_types",
            resource_types,
        )

    @property
    def profile_key(self) -> str:
        return "public-browser"

    @property
    def profile_fingerprint(self) -> str:
        payload = {
            "version": 1,
            "mode": "public-browser",
            "engine": self.engine,
            "playwright_version": self.playwright_version,
            "locale": self.locale,
            "viewport": [
                self.viewport_width,
                self.viewport_height,
            ],
            "blocked_resource_types": self.blocked_resource_types,
            "settle_timeout_seconds": self.settle_timeout_seconds,
            "max_requests": self.max_requests,
            "max_total_wire_bytes": self.max_total_wire_bytes,
            "max_total_decoded_bytes": self.max_total_decoded_bytes,
            "max_rendered_dom_bytes": self.max_rendered_dom_bytes,
            "http_profile_fingerprint": (
                self.http_policy.profile_fingerprint
            ),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "public-browser:v1:" + hashlib.sha256(encoded).hexdigest()

    @property
    def policy_fingerprint(self) -> str:
        payload = {
            "version": 1,
            "browser_profile": self.profile_fingerprint,
            "http_policy_fingerprint": (
                self.http_policy.policy_fingerprint
            ),
            "sink_proxy": self.sink_proxy,
            "service_workers": "block",
            "websockets": "block",
            "unsafe_methods": "block",
            "webrtc": "block",
            "webtransport": "block",
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "observer-browser:v1:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class BrowserResourceRequest:
    url: str
    method: str
    headers: Mapping[str, str]
    resource_type: str
    is_main_navigation: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "url",
            _required_text("url", self.url),
        )
        object.__setattr__(
            self,
            "method",
            _required_text("method", self.method).upper(),
        )
        object.__setattr__(
            self,
            "resource_type",
            _required_text(
                "resource_type",
                self.resource_type,
            ).lower(),
        )
        if not isinstance(self.is_main_navigation, bool):
            raise ObserverContractError(
                "is_main_navigation must be boolean"
            )
        if not isinstance(self.headers, Mapping):
            raise ObserverContractError(
                "headers must be a mapping"
            )
        object.__setattr__(
            self,
            "headers",
            MappingProxyType(
                {
                    str(key).lower(): str(value)
                    for key, value in self.headers.items()
                }
            ),
        )


BrowserResourceLoader = Callable[
    [BrowserResourceRequest],
    SafeHttpResourceResult,
]


@dataclass(frozen=True, slots=True)
class BrowserRenderResult:
    final_locator: str
    response_status: int
    rendered_dom: bytes
    main_response_body: bytes
    main_response_headers: Mapping[str, str]
    redirect_count: int
    incomplete: bool = False
    retry_at: Optional[object] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "final_locator",
            _required_text("final_locator", self.final_locator),
        )
        if (
            not isinstance(self.response_status, int)
            or isinstance(self.response_status, bool)
            or not 100 <= self.response_status <= 599
        ):
            raise ObserverContractError(
                "response_status must be a valid HTTP status"
            )
        if not isinstance(self.rendered_dom, bytes):
            raise ObserverContractError(
                "rendered_dom must be bytes"
            )
        if not isinstance(self.main_response_body, bytes):
            raise ObserverContractError(
                "main_response_body must be bytes"
            )
        if not isinstance(self.main_response_headers, Mapping):
            raise ObserverContractError(
                "main_response_headers must be a mapping"
            )
        object.__setattr__(
            self,
            "main_response_headers",
            MappingProxyType(
                {
                    str(key).lower(): str(value)
                    for key, value in self.main_response_headers.items()
                }
            ),
        )
        object.__setattr__(
            self,
            "redirect_count",
            _positive_int(
                "redirect_count",
                self.redirect_count,
                allow_zero=True,
            ),
        )
        if not isinstance(self.incomplete, bool):
            raise ObserverContractError(
                "incomplete must be boolean"
            )


class BrowserRenderFailure(Exception):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
        retry_at=None,
    ) -> None:
        self.code = _required_text("code", code)
        self.retryable = bool(retryable)
        self.retry_at = retry_at
        super().__init__(self.code)
