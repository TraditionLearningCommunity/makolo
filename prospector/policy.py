from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from .errors import ProspectorContractError

BUDGET_SCOPE_KINDS = frozenset({"host", "domain", "mission", "campaign", "branch"})

DEFAULT_SENSITIVE_QUERY_NAMES = (
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "password",
    "passwd",
    "secret",
    "session",
    "sessionid",
    "token",
)


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ProspectorContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ProspectorContractError(f"{name} must not be empty")
    return value


def _suffixes(values) -> Tuple[str, ...]:
    result = []
    for value in tuple(values or ()):
        value = _required_text("host suffix", value).lower().lstrip(".")
        try:
            value = value.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ProspectorContractError("host suffix must be valid IDNA") from exc
        if value not in result:
            result.append(value)
    return tuple(result)


class GateDisposition(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class BudgetPolicy:
    period_seconds: int
    limits: Mapping[str, int]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.period_seconds, int)
            or isinstance(self.period_seconds, bool)
            or self.period_seconds < 1
        ):
            raise ProspectorContractError("period_seconds must be a positive integer")
        if not isinstance(self.limits, Mapping):
            raise ProspectorContractError("budget limits must be a mapping")
        limits = {}
        for scope_kind, value in self.limits.items():
            if scope_kind not in BUDGET_SCOPE_KINDS:
                raise ProspectorContractError(
                    f"unsupported budget scope kind {scope_kind!r}"
                )
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
            ):
                raise ProspectorContractError(
                    f"budget limit for {scope_kind} must be a positive integer"
                )
            limits[scope_kind] = value
        if not limits:
            raise ProspectorContractError("budget limits must not be empty")
        object.__setattr__(self, "limits", MappingProxyType(limits))


@dataclass(frozen=True, slots=True)
class ObservationPolicy:
    policy_key: str
    dns_retry_seconds: int
    allowed_kinds: Tuple[str, ...] = ("web_url",)
    allowed_host_suffixes: Tuple[str, ...] = ()
    denied_host_suffixes: Tuple[str, ...] = ()
    denied_path_prefixes: Tuple[str, ...] = ()
    sensitive_query_names: Tuple[str, ...] = DEFAULT_SENSITIVE_QUERY_NAMES
    max_depth: Optional[int] = None
    max_locator_length: Optional[int] = None
    budget: Optional[BudgetPolicy] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_key", _required_text("policy_key", self.policy_key))
        if (
            not isinstance(self.dns_retry_seconds, int)
            or isinstance(self.dns_retry_seconds, bool)
            or self.dns_retry_seconds < 1
        ):
            raise ProspectorContractError(
                "dns_retry_seconds must be a positive integer"
            )
        kinds = tuple(
            _required_text("allowed kind", value)
            for value in tuple(self.allowed_kinds)
        )
        if not kinds:
            raise ProspectorContractError("allowed_kinds must not be empty")
        object.__setattr__(self, "allowed_kinds", kinds)
        object.__setattr__(
            self,
            "allowed_host_suffixes",
            _suffixes(self.allowed_host_suffixes),
        )
        object.__setattr__(
            self,
            "denied_host_suffixes",
            _suffixes(self.denied_host_suffixes),
        )
        prefixes = tuple(
            _required_text("denied_path_prefix", value)
            for value in tuple(self.denied_path_prefixes)
        )
        object.__setattr__(self, "denied_path_prefixes", prefixes)
        sensitive = tuple(
            _required_text("sensitive_query_name", value).lower()
            for value in tuple(self.sensitive_query_names)
        )
        object.__setattr__(self, "sensitive_query_names", sensitive)
        if self.max_depth is not None and (
            not isinstance(self.max_depth, int)
            or isinstance(self.max_depth, bool)
            or self.max_depth < 0
        ):
            raise ProspectorContractError("max_depth must be a non-negative integer")
        if self.max_locator_length is not None and (
            not isinstance(self.max_locator_length, int)
            or isinstance(self.max_locator_length, bool)
            or self.max_locator_length < 1
        ):
            raise ProspectorContractError(
                "max_locator_length must be a positive integer"
            )


@dataclass(frozen=True, slots=True)
class GateDecision:
    disposition: GateDisposition
    reason_code: str
    retry_at: Optional[datetime] = None
    budget_scopes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            disposition = GateDisposition(self.disposition)
        except ValueError as exc:
            raise ProspectorContractError("invalid gate disposition") from exc
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "reason_code", _required_text("reason_code", self.reason_code))
        if self.retry_at is not None:
            if self.retry_at.tzinfo is None or self.retry_at.utcoffset() is None:
                raise ProspectorContractError("retry_at must be timezone-aware")
            object.__setattr__(
                self,
                "retry_at",
                self.retry_at.astimezone(timezone.utc),
            )
        if disposition is GateDisposition.DEFER and self.retry_at is None:
            raise ProspectorContractError("deferred gate decision requires retry_at")
        if disposition is not GateDisposition.DEFER and self.retry_at is not None:
            raise ProspectorContractError(
                "only deferred gate decisions may carry retry_at"
            )
        object.__setattr__(
            self,
            "budget_scopes",
            MappingProxyType(dict(self.budget_scopes)),
        )
