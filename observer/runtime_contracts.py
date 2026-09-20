from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .contracts import ObservationOutcome
from .errors import ObserverContractError


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ObserverContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ObserverContractError(f"{name} must not be empty")
    return value


def _aware(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ObserverContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ObserverContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ObserverRuntimePolicy:
    profile_key: str = "public-http"
    profile_fingerprint: str = "public-http-v1"
    policy_fingerprint: str = "observer-runtime-v1"
    lease_seconds: int = 300
    recovery_retry_seconds: int = 60

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_key", _required_text("profile_key", self.profile_key))
        object.__setattr__(
            self,
            "profile_fingerprint",
            _required_text("profile_fingerprint", self.profile_fingerprint),
        )
        object.__setattr__(
            self,
            "policy_fingerprint",
            _required_text("policy_fingerprint", self.policy_fingerprint),
        )
        for name in ("lease_seconds", "recovery_retry_seconds"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ObserverContractError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class ObservationClaim:
    observation_ref: str
    claim_token: str
    worker_id: str
    leased_until: datetime
    target_key: str
    kind: str
    locator: str
    source_handoff_key: str
    source_handoff_generation: int

    def __post_init__(self) -> None:
        for name in (
            "observation_ref",
            "claim_token",
            "worker_id",
            "target_key",
            "kind",
            "locator",
            "source_handoff_key",
        ):
            object.__setattr__(self, name, _required_text(name, getattr(self, name)))
        object.__setattr__(self, "leased_until", _aware("leased_until", self.leased_until))
        if (
            not isinstance(self.source_handoff_generation, int)
            or isinstance(self.source_handoff_generation, bool)
            or self.source_handoff_generation < 1
        ):
            raise ObserverContractError(
                "source_handoff_generation must be a positive integer"
            )


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    outcome: ObservationOutcome
    observed_at: datetime
    final_locator: Optional[str] = None
    response_status: Optional[int] = None
    failure_code: Optional[str] = None
    retry_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        try:
            outcome = ObservationOutcome(self.outcome)
        except ValueError as exc:
            raise ObserverContractError("invalid acquisition outcome") from exc
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "observed_at", _aware("observed_at", self.observed_at))
        if self.final_locator is not None:
            object.__setattr__(
                self,
                "final_locator",
                _required_text("final_locator", self.final_locator),
            )
        if self.response_status is not None and (
            not isinstance(self.response_status, int)
            or isinstance(self.response_status, bool)
            or not 100 <= self.response_status <= 599
        ):
            raise ObserverContractError("response_status must be a valid HTTP status")
        if self.retry_at is not None:
            object.__setattr__(self, "retry_at", _aware("retry_at", self.retry_at))
        if outcome is ObservationOutcome.FAILED:
            object.__setattr__(
                self,
                "failure_code",
                _required_text("failure_code", self.failure_code),
            )
        elif self.failure_code is not None or self.retry_at is not None:
            raise ObserverContractError(
                "successful acquisition must not carry failure_code or retry_at"
            )
