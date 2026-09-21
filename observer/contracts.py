from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple

from .errors import ObserverContractError

OBSERVER_MATERIAL_CONTRACT_VERSION = 2


class ObservationTrigger(str, Enum):
    HANDOFF = "handoff"
    RETRY = "retry"
    WATCH = "watch"


class ObservationLifecycle(str, Enum):
    OPEN = "open"
    FINALIZED = "finalized"


class ObservationOutcome(str, Enum):
    OBSERVED = "observed"
    NOT_MODIFIED = "not_modified"
    FAILED = "failed"


class AttemptStrategy(str, Enum):
    DIRECT_HTTP = "direct_http"
    BROWSER_RENDER = "browser_render"


class AttemptLifecycle(str, Enum):
    OPEN = "open"
    FINALIZED = "finalized"


class AttemptOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


class ArtifactOrigin(str, Enum):
    CAPTURED = "captured"
    RENDERED = "rendered"
    DERIVED = "derived"


class ArtifactCompleteness(str, Enum):
    COMPLETE = "complete"
    TRUNCATED = "truncated"
    INCOMPLETE = "incomplete"


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
    value = value.strip()
    return _required_text(name, value) if value else None


def _aware(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ObserverContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ObserverContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _optional_aware(name: str, value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return _aware(name, value)


def _positive_generation(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ObserverContractError(
            "source_handoff_generation must be a positive integer"
        )
    return value


def _non_negative_int(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ObserverContractError(f"{name} must be a non-negative integer")
    return value


def _http_status(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 100 <= value <= 599
    ):
        raise ObserverContractError("response_status must be a valid HTTP status")
    return value


def _sha256(name: str, value: str) -> str:
    value = _required_text(name, value).lower()
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ObserverContractError(
            f"{name} must be a lowercase SHA-256 hex digest"
        )
    return value


def make_material_key(
    *,
    observation_ref: str,
    contract_version: int = OBSERVER_MATERIAL_CONTRACT_VERSION,
) -> str:
    observation_ref = _required_text("observation_ref", observation_ref)
    if contract_version != OBSERVER_MATERIAL_CONTRACT_VERSION:
        raise ObserverContractError(
            f"unsupported material contract version {contract_version}"
        )
    payload = f"{observation_ref}\0{contract_version}".encode("utf-8")
    return (
        f"observer-material:v{contract_version}:"
        f"{hashlib.sha256(payload).hexdigest()}"
    )


@dataclass(frozen=True, slots=True)
class TransformationDescriptor:
    name: str
    version: Optional[str] = None
    fingerprint: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "name",
            _required_text("transformation.name", self.name),
        )
        object.__setattr__(
            self,
            "version",
            _optional_text("transformation.version", self.version),
        )
        object.__setattr__(
            self,
            "fingerprint",
            _optional_text("transformation.fingerprint", self.fingerprint),
        )
        if self.version is None and self.fingerprint is None:
            raise ObserverContractError(
                "transformation requires a version or fingerprint"
            )


@dataclass(frozen=True, slots=True)
class Observation:
    observation_ref: str
    target_key: str
    source_handoff_key: str
    source_handoff_generation: int
    trigger: ObservationTrigger
    lifecycle: ObservationLifecycle
    started_at: datetime
    requested_locator: str
    observation_profile_ref: str
    observation_profile_fingerprint: str
    policy_fingerprint: str
    observed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    outcome: Optional[ObservationOutcome] = None
    final_locator: Optional[str] = None
    response_status: Optional[int] = None
    failure_code: Optional[str] = None
    retry_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation_ref",
            _required_text("observation_ref", self.observation_ref),
        )
        object.__setattr__(
            self,
            "target_key",
            _required_text("target_key", self.target_key),
        )
        object.__setattr__(
            self,
            "source_handoff_key",
            _required_text("source_handoff_key", self.source_handoff_key),
        )
        object.__setattr__(
            self,
            "source_handoff_generation",
            _positive_generation(self.source_handoff_generation),
        )
        object.__setattr__(
            self,
            "requested_locator",
            _required_text("requested_locator", self.requested_locator),
        )
        object.__setattr__(
            self,
            "observation_profile_ref",
            _required_text(
                "observation_profile_ref",
                self.observation_profile_ref,
            ),
        )
        object.__setattr__(
            self,
            "observation_profile_fingerprint",
            _required_text(
                "observation_profile_fingerprint",
                self.observation_profile_fingerprint,
            ),
        )
        object.__setattr__(
            self,
            "policy_fingerprint",
            _required_text("policy_fingerprint", self.policy_fingerprint),
        )
        object.__setattr__(
            self,
            "started_at",
            _aware("started_at", self.started_at),
        )
        object.__setattr__(
            self,
            "observed_at",
            _optional_aware("observed_at", self.observed_at),
        )
        object.__setattr__(
            self,
            "completed_at",
            _optional_aware("completed_at", self.completed_at),
        )
        object.__setattr__(
            self,
            "final_locator",
            _optional_text("final_locator", self.final_locator),
        )
        object.__setattr__(
            self,
            "response_status",
            _http_status(self.response_status),
        )
        object.__setattr__(
            self,
            "failure_code",
            _optional_text("failure_code", self.failure_code),
        )
        object.__setattr__(
            self,
            "retry_at",
            _optional_aware("retry_at", self.retry_at),
        )
        try:
            trigger = ObservationTrigger(self.trigger)
            lifecycle = ObservationLifecycle(self.lifecycle)
        except ValueError as exc:
            raise ObserverContractError(
                "invalid observation trigger or lifecycle"
            ) from exc
        object.__setattr__(self, "trigger", trigger)
        object.__setattr__(self, "lifecycle", lifecycle)
        outcome = None
        if self.outcome is not None:
            try:
                outcome = ObservationOutcome(self.outcome)
            except ValueError as exc:
                raise ObserverContractError(
                    "invalid observation outcome"
                ) from exc
            object.__setattr__(self, "outcome", outcome)

        if lifecycle is ObservationLifecycle.OPEN:
            if self.completed_at is not None or outcome is not None:
                raise ObserverContractError(
                    "open observation cannot be completed"
                )
            if self.failure_code is not None or self.retry_at is not None:
                raise ObserverContractError(
                    "open observation cannot carry terminal failure data"
                )
        else:
            if (
                self.completed_at is None
                or self.observed_at is None
                or outcome is None
            ):
                raise ObserverContractError(
                    "finalized observation requires observed_at, completed_at and outcome"
                )
            if self.completed_at < self.started_at:
                raise ObserverContractError(
                    "completed_at must not precede started_at"
                )
            if outcome is ObservationOutcome.FAILED:
                if self.failure_code is None:
                    raise ObserverContractError(
                        "failed observation requires failure_code"
                    )
            elif self.failure_code is not None or self.retry_at is not None:
                raise ObserverContractError(
                    "successful observation must not carry failure_code or retry_at"
                )


@dataclass(frozen=True, slots=True)
class ObservationAttempt:
    attempt_ref: str
    observation_ref: str
    ordinal: int
    strategy: AttemptStrategy
    lifecycle: AttemptLifecycle
    started_at: datetime
    requested_locator: str
    completed_at: Optional[datetime] = None
    outcome: Optional[AttemptOutcome] = None
    final_locator: Optional[str] = None
    response_status: Optional[int] = None
    failure_code: Optional[str] = None
    retry_after_at: Optional[datetime] = None
    redirect_count: int = 0
    wire_bytes: int = 0
    decoded_bytes: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "attempt_ref",
            _required_text("attempt_ref", self.attempt_ref),
        )
        object.__setattr__(
            self,
            "observation_ref",
            _required_text("observation_ref", self.observation_ref),
        )
        if (
            not isinstance(self.ordinal, int)
            or isinstance(self.ordinal, bool)
            or self.ordinal < 1
        ):
            raise ObserverContractError("ordinal must be a positive integer")
        try:
            strategy = AttemptStrategy(self.strategy)
            lifecycle = AttemptLifecycle(self.lifecycle)
        except ValueError as exc:
            raise ObserverContractError(
                "invalid attempt strategy or lifecycle"
            ) from exc
        object.__setattr__(self, "strategy", strategy)
        object.__setattr__(self, "lifecycle", lifecycle)
        object.__setattr__(
            self,
            "started_at",
            _aware("started_at", self.started_at),
        )
        object.__setattr__(
            self,
            "completed_at",
            _optional_aware("completed_at", self.completed_at),
        )
        object.__setattr__(
            self,
            "requested_locator",
            _required_text("requested_locator", self.requested_locator),
        )
        object.__setattr__(
            self,
            "final_locator",
            _optional_text("final_locator", self.final_locator),
        )
        object.__setattr__(
            self,
            "response_status",
            _http_status(self.response_status),
        )
        object.__setattr__(
            self,
            "failure_code",
            _optional_text("failure_code", self.failure_code),
        )
        object.__setattr__(
            self,
            "retry_after_at",
            _optional_aware("retry_after_at", self.retry_after_at),
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
        outcome = None
        if self.outcome is not None:
            try:
                outcome = AttemptOutcome(self.outcome)
            except ValueError as exc:
                raise ObserverContractError(
                    "invalid attempt outcome"
                ) from exc
            object.__setattr__(self, "outcome", outcome)
        if lifecycle is AttemptLifecycle.OPEN:
            if self.completed_at is not None or outcome is not None:
                raise ObserverContractError(
                    "open attempt cannot be completed"
                )
        else:
            if self.completed_at is None or outcome is None:
                raise ObserverContractError(
                    "finalized attempt requires completed_at and outcome"
                )
            if self.completed_at < self.started_at:
                raise ObserverContractError(
                    "attempt completed_at must not precede started_at"
                )
            if (
                outcome is AttemptOutcome.FAILED
                and self.failure_code is None
            ):
                raise ObserverContractError(
                    "failed attempt requires failure_code"
                )


@dataclass(frozen=True, slots=True)
class ObservedArtifact:
    artifact_ref: str
    observation_ref: str
    role: str
    origin: ArtifactOrigin
    completeness: ArtifactCompleteness
    byte_length: int
    content_digest: str
    captured_at: datetime
    producing_attempt_ref: Optional[str] = None
    declared_media_type: Optional[str] = None
    detected_media_type: Optional[str] = None
    charset: Optional[str] = None
    source_artifact_ref: Optional[str] = None
    transformation: Optional[TransformationDescriptor] = None
    protection_context_ref: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "artifact_ref",
            _required_text("artifact_ref", self.artifact_ref),
        )
        object.__setattr__(
            self,
            "observation_ref",
            _required_text("observation_ref", self.observation_ref),
        )
        object.__setattr__(
            self,
            "role",
            _required_text("role", self.role),
        )
        try:
            origin = ArtifactOrigin(self.origin)
            completeness = ArtifactCompleteness(self.completeness)
        except ValueError as exc:
            raise ObserverContractError(
                "invalid artifact origin or completeness"
            ) from exc
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "completeness", completeness)
        object.__setattr__(
            self,
            "byte_length",
            _non_negative_int("byte_length", self.byte_length),
        )
        object.__setattr__(
            self,
            "content_digest",
            _sha256("content_digest", self.content_digest),
        )
        object.__setattr__(
            self,
            "captured_at",
            _aware("captured_at", self.captured_at),
        )
        object.__setattr__(
            self,
            "producing_attempt_ref",
            _optional_text(
                "producing_attempt_ref",
                self.producing_attempt_ref,
            ),
        )
        object.__setattr__(
            self,
            "declared_media_type",
            _optional_text(
                "declared_media_type",
                self.declared_media_type,
            ),
        )
        object.__setattr__(
            self,
            "detected_media_type",
            _optional_text(
                "detected_media_type",
                self.detected_media_type,
            ),
        )
        object.__setattr__(
            self,
            "charset",
            _optional_text("charset", self.charset),
        )
        object.__setattr__(
            self,
            "source_artifact_ref",
            _optional_text(
                "source_artifact_ref",
                self.source_artifact_ref,
            ),
        )
        object.__setattr__(
            self,
            "protection_context_ref",
            _optional_text(
                "protection_context_ref",
                self.protection_context_ref,
            ),
        )
        if origin is ArtifactOrigin.DERIVED:
            if (
                self.source_artifact_ref is None
                or self.transformation is None
            ):
                raise ObserverContractError(
                    "derived artifact requires source_artifact_ref and transformation"
                )
        elif self.transformation is not None:
            raise ObserverContractError(
                "only derived artifacts may carry transformation metadata"
            )

    def to_descriptor(self) -> "ArtifactDescriptor":
        return ArtifactDescriptor(
            artifact_ref=self.artifact_ref,
            observation_ref=self.observation_ref,
            producing_attempt_ref=self.producing_attempt_ref,
            role=self.role,
            origin=self.origin,
            completeness=self.completeness,
            declared_media_type=self.declared_media_type,
            detected_media_type=self.detected_media_type,
            charset=self.charset,
            byte_length=self.byte_length,
            content_digest=self.content_digest,
            captured_at=self.captured_at,
            source_artifact_ref=self.source_artifact_ref,
            transformation=self.transformation,
            protection_context_ref=self.protection_context_ref,
        )


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    artifact_ref: str
    observation_ref: str
    role: str
    origin: ArtifactOrigin
    completeness: ArtifactCompleteness
    byte_length: int
    content_digest: str
    captured_at: datetime
    producing_attempt_ref: Optional[str] = None
    declared_media_type: Optional[str] = None
    detected_media_type: Optional[str] = None
    charset: Optional[str] = None
    source_artifact_ref: Optional[str] = None
    transformation: Optional[TransformationDescriptor] = None
    protection_context_ref: Optional[str] = None

    def __post_init__(self) -> None:
        probe = ObservedArtifact(
            artifact_ref=self.artifact_ref,
            observation_ref=self.observation_ref,
            producing_attempt_ref=self.producing_attempt_ref,
            role=self.role,
            origin=self.origin,
            completeness=self.completeness,
            declared_media_type=self.declared_media_type,
            detected_media_type=self.detected_media_type,
            charset=self.charset,
            byte_length=self.byte_length,
            content_digest=self.content_digest,
            captured_at=self.captured_at,
            source_artifact_ref=self.source_artifact_ref,
            transformation=self.transformation,
            protection_context_ref=self.protection_context_ref,
        )
        for field_name in (
            "artifact_ref",
            "observation_ref",
            "producing_attempt_ref",
            "role",
            "origin",
            "completeness",
            "declared_media_type",
            "detected_media_type",
            "charset",
            "byte_length",
            "content_digest",
            "captured_at",
            "source_artifact_ref",
            "transformation",
            "protection_context_ref",
        ):
            object.__setattr__(
                self,
                field_name,
                getattr(probe, field_name),
            )


@dataclass(frozen=True, slots=True)
class ObservationMaterial:
    material_key: str
    observation_ref: str
    target_key: str
    target_kind: str
    source_handoff_key: str
    source_handoff_generation: int
    trigger: ObservationTrigger
    started_at: datetime
    observed_at: datetime
    completed_at: datetime
    requested_locator: str
    observation_profile_ref: str
    observation_profile_fingerprint: str
    policy_fingerprint: str
    outcome: ObservationOutcome
    attempts: Tuple[ObservationAttempt, ...] = ()
    artifacts: Tuple[ArtifactDescriptor, ...] = ()
    revalidated_artifacts: Tuple[ArtifactDescriptor, ...] = ()
    final_locator: Optional[str] = None
    response_status: Optional[int] = None
    failure_code: Optional[str] = None
    contract_version: int = OBSERVER_MATERIAL_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation_ref",
            _required_text("observation_ref", self.observation_ref),
        )
        expected = make_material_key(
            observation_ref=self.observation_ref,
            contract_version=self.contract_version,
        )
        if self.material_key != expected:
            raise ObserverContractError(
                "material_key is inconsistent with observation_ref"
            )
        object.__setattr__(
            self,
            "target_key",
            _required_text("target_key", self.target_key),
        )
        object.__setattr__(
            self,
            "target_kind",
            _required_text("target_kind", self.target_kind),
        )
        object.__setattr__(
            self,
            "source_handoff_key",
            _required_text(
                "source_handoff_key", self.source_handoff_key
            ),
        )
        object.__setattr__(
            self,
            "source_handoff_generation",
            _positive_generation(self.source_handoff_generation),
        )
        try:
            trigger = ObservationTrigger(self.trigger)
        except ValueError as exc:
            raise ObserverContractError("invalid material trigger") from exc
        object.__setattr__(self, "trigger", trigger)
        object.__setattr__(
            self,
            "started_at",
            _aware("started_at", self.started_at),
        )
        object.__setattr__(
            self,
            "observed_at",
            _aware("observed_at", self.observed_at),
        )
        object.__setattr__(
            self,
            "completed_at",
            _aware("completed_at", self.completed_at),
        )
        if self.observed_at < self.started_at:
            raise ObserverContractError(
                "material observed_at must not precede started_at"
            )
        if self.completed_at < self.observed_at:
            raise ObserverContractError(
                "material completed_at must not precede observed_at"
            )
        object.__setattr__(
            self,
            "requested_locator",
            _required_text("requested_locator", self.requested_locator),
        )
        object.__setattr__(
            self,
            "final_locator",
            _optional_text("final_locator", self.final_locator),
        )
        object.__setattr__(
            self,
            "observation_profile_ref",
            _required_text(
                "observation_profile_ref",
                self.observation_profile_ref,
            ),
        )
        object.__setattr__(
            self,
            "observation_profile_fingerprint",
            _required_text(
                "observation_profile_fingerprint",
                self.observation_profile_fingerprint,
            ),
        )
        object.__setattr__(
            self,
            "policy_fingerprint",
            _required_text(
                "policy_fingerprint", self.policy_fingerprint
            ),
        )
        object.__setattr__(
            self,
            "response_status",
            _http_status(self.response_status),
        )
        object.__setattr__(
            self,
            "failure_code",
            _optional_text("failure_code", self.failure_code),
        )
        try:
            outcome = ObservationOutcome(self.outcome)
        except ValueError as exc:
            raise ObserverContractError(
                "invalid material outcome"
            ) from exc
        object.__setattr__(self, "outcome", outcome)

        attempts = tuple(self.attempts)
        if not all(
            isinstance(item, ObservationAttempt)
            for item in attempts
        ):
            raise ObserverContractError(
                "attempts must contain ObservationAttempt values"
            )
        if any(
            item.observation_ref != self.observation_ref
            for item in attempts
        ):
            raise ObserverContractError(
                "attempts must belong to the material observation"
            )
        ordinals = tuple(item.ordinal for item in attempts)
        if tuple(sorted(ordinals)) != ordinals or len(set(ordinals)) != len(
            ordinals
        ):
            raise ObserverContractError(
                "attempts must have unique ascending ordinals"
            )
        if any(
            item.lifecycle is not AttemptLifecycle.FINALIZED
            for item in attempts
        ):
            raise ObserverContractError(
                "material may expose only finalized attempts"
            )
        object.__setattr__(self, "attempts", attempts)

        artifacts = tuple(self.artifacts)
        revalidated = tuple(self.revalidated_artifacts)
        if not all(
            isinstance(item, ArtifactDescriptor)
            for item in artifacts + revalidated
        ):
            raise ObserverContractError(
                "material artifacts must contain ArtifactDescriptor values"
            )
        if any(
            item.observation_ref != self.observation_ref
            for item in artifacts
        ):
            raise ObserverContractError(
                "new artifacts must belong to the material observation"
            )
        current_attempt_refs = {
            item.attempt_ref
            for item in attempts
        }
        if any(
            item.producing_attempt_ref is not None
            and item.producing_attempt_ref not in current_attempt_refs
            for item in artifacts
        ):
            raise ObserverContractError(
                "artifact attempt provenance must reference this observation"
            )
        artifact_refs = tuple(item.artifact_ref for item in artifacts)
        revalidated_refs = tuple(
            item.artifact_ref for item in revalidated
        )
        if len(set(artifact_refs)) != len(artifact_refs):
            raise ObserverContractError(
                "artifact references must be unique"
            )
        if len(set(revalidated_refs)) != len(revalidated_refs):
            raise ObserverContractError(
                "revalidated artifact references must be unique"
            )
        if set(artifact_refs) & set(revalidated_refs):
            raise ObserverContractError(
                "new and revalidated artifacts must be disjoint"
            )
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(
            self,
            "revalidated_artifacts",
            revalidated,
        )

        if outcome is ObservationOutcome.FAILED:
            if self.failure_code is None:
                raise ObserverContractError(
                    "failed material requires failure_code"
                )
        elif self.failure_code is not None:
            raise ObserverContractError(
                "successful material must not carry failure_code"
            )
        if outcome is ObservationOutcome.NOT_MODIFIED:
            if artifacts:
                raise ObserverContractError(
                    "not_modified material must not create artifacts"
                )
            if not revalidated:
                raise ObserverContractError(
                    "not_modified material requires revalidated artifacts"
                )

    @property
    def revalidated_artifact_refs(self) -> Tuple[str, ...]:
        return tuple(
            item.artifact_ref
            for item in self.revalidated_artifacts
        )
