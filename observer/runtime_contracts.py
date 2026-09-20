from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from .contracts import (
    ArtifactCompleteness,
    ArtifactOrigin,
    ObservationOutcome,
)
from .errors import ObserverContractError


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ObserverContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ObserverContractError(f"{name} must not be empty")
    return value


def _optional_text(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ObserverContractError(f"{name} must be a string")
    value = value.strip()
    return value or None


def _aware(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ObserverContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ObserverContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _non_negative_int(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ObserverContractError(
            f"{name} must be a non-negative integer"
        )
    return value


@dataclass(frozen=True, slots=True)
class ObserverRuntimePolicy:
    profile_key: str = "public-http"
    profile_fingerprint: str = "public-http-v1"
    policy_fingerprint: str = "observer-runtime-v1"
    lease_seconds: int = 300
    recovery_retry_seconds: int = 60
    watch_interval_seconds: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "profile_key",
            _required_text("profile_key", self.profile_key),
        )
        object.__setattr__(
            self,
            "profile_fingerprint",
            _required_text(
                "profile_fingerprint",
                self.profile_fingerprint,
            ),
        )
        object.__setattr__(
            self,
            "policy_fingerprint",
            _required_text(
                "policy_fingerprint",
                self.policy_fingerprint,
            ),
        )
        for name in ("lease_seconds", "recovery_retry_seconds"):
            value = getattr(self, name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
            ):
                raise ObserverContractError(
                    f"{name} must be a positive integer"
                )
        if self.watch_interval_seconds is not None and (
            not isinstance(self.watch_interval_seconds, int)
            or isinstance(self.watch_interval_seconds, bool)
            or self.watch_interval_seconds < 1
        ):
            raise ObserverContractError(
                "watch_interval_seconds must be a positive integer"
            )


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
            object.__setattr__(
                self,
                name,
                _required_text(name, getattr(self, name)),
            )
        object.__setattr__(
            self,
            "leased_until",
            _aware("leased_until", self.leased_until),
        )
        if (
            not isinstance(self.source_handoff_generation, int)
            or isinstance(self.source_handoff_generation, bool)
            or self.source_handoff_generation < 1
        ):
            raise ObserverContractError(
                "source_handoff_generation must be a positive integer"
            )


@dataclass(frozen=True, slots=True)
class ObservationBacklog:
    pending_handoffs: int
    due_retries: int
    due_watches: int
    open_observations: int

    def __post_init__(self) -> None:
        for name in (
            "pending_handoffs",
            "due_retries",
            "due_watches",
            "open_observations",
        ):
            value = getattr(self, name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise ObserverContractError(
                    f"{name} must be a non-negative integer"
                )


@dataclass(frozen=True, slots=True)
class AcquiredArtifact:
    content: bytes
    role: str
    captured_at: datetime
    origin: ArtifactOrigin = ArtifactOrigin.CAPTURED
    completeness: ArtifactCompleteness = ArtifactCompleteness.COMPLETE
    declared_media_type: Optional[str] = None
    detected_media_type: Optional[str] = None
    charset: Optional[str] = None
    protection_context_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.content, bytes):
            raise ObserverContractError(
                "acquired artifact content must be bytes"
            )
        object.__setattr__(
            self,
            "role",
            _required_text("role", self.role),
        )
        object.__setattr__(
            self,
            "captured_at",
            _aware("captured_at", self.captured_at),
        )
        try:
            origin = ArtifactOrigin(self.origin)
            completeness = ArtifactCompleteness(self.completeness)
        except ValueError as exc:
            raise ObserverContractError(
                "invalid acquired artifact origin or completeness"
            ) from exc
        if origin is ArtifactOrigin.DERIVED:
            raise ObserverContractError(
                "acquisition results may not smuggle derived artifacts"
            )
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "completeness", completeness)
        for name in (
            "declared_media_type",
            "detected_media_type",
            "charset",
            "protection_context_ref",
        ):
            object.__setattr__(
                self,
                name,
                _optional_text(name, getattr(self, name)),
            )


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    outcome: ObservationOutcome
    observed_at: datetime
    final_locator: Optional[str] = None
    response_status: Optional[int] = None
    failure_code: Optional[str] = None
    retry_at: Optional[datetime] = None
    artifacts: Tuple[AcquiredArtifact, ...] = ()
    revalidated_artifact_ref: Optional[str] = None
    validator_etag: Optional[str] = None
    validator_last_modified: Optional[str] = None
    redirect_count: int = 0
    wire_bytes: int = 0
    decoded_bytes: int = 0

    def __post_init__(self) -> None:
        try:
            outcome = ObservationOutcome(self.outcome)
        except ValueError as exc:
            raise ObserverContractError(
                "invalid acquisition outcome"
            ) from exc
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(
            self,
            "observed_at",
            _aware("observed_at", self.observed_at),
        )
        object.__setattr__(
            self,
            "final_locator",
            _optional_text("final_locator", self.final_locator),
        )
        if self.response_status is not None and (
            not isinstance(self.response_status, int)
            or isinstance(self.response_status, bool)
            or not 100 <= self.response_status <= 599
        ):
            raise ObserverContractError(
                "response_status must be a valid HTTP status"
            )
        if self.retry_at is not None:
            object.__setattr__(
                self,
                "retry_at",
                _aware("retry_at", self.retry_at),
            )
        object.__setattr__(
            self,
            "revalidated_artifact_ref",
            _optional_text(
                "revalidated_artifact_ref",
                self.revalidated_artifact_ref,
            ),
        )
        object.__setattr__(
            self,
            "validator_etag",
            _optional_text("validator_etag", self.validator_etag),
        )
        object.__setattr__(
            self,
            "validator_last_modified",
            _optional_text(
                "validator_last_modified",
                self.validator_last_modified,
            ),
        )
        object.__setattr__(
            self,
            "redirect_count",
            _non_negative_int("redirect_count", self.redirect_count),
        )
        object.__setattr__(
            self,
            "wire_bytes",
            _non_negative_int("wire_bytes", self.wire_bytes),
        )
        object.__setattr__(
            self,
            "decoded_bytes",
            _non_negative_int("decoded_bytes", self.decoded_bytes),
        )
        artifacts = tuple(self.artifacts)
        if not all(isinstance(item, AcquiredArtifact) for item in artifacts):
            raise ObserverContractError(
                "artifacts must contain AcquiredArtifact values"
            )
        object.__setattr__(self, "artifacts", artifacts)

        if outcome is ObservationOutcome.FAILED:
            object.__setattr__(
                self,
                "failure_code",
                _required_text("failure_code", self.failure_code),
            )
            if artifacts or self.revalidated_artifact_ref is not None:
                raise ObserverContractError(
                    "failed acquisition must not expose interpretation material"
                )
        else:
            if self.failure_code is not None or self.retry_at is not None:
                raise ObserverContractError(
                    "successful acquisition must not carry failure_code or retry_at"
                )
            if (
                outcome is ObservationOutcome.NOT_MODIFIED
                and artifacts
            ):
                raise ObserverContractError(
                    "not-modified acquisition must not create new artifacts"
                )
