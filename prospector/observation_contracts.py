from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from .errors import ObservationContractError
from .frontier import FrontierClaim

OBSERVATION_CONTRACT_VERSION = 1


class ObservationDisposition(str, Enum):
    ACCEPTED = "accepted"
    ALREADY_ACCEPTED = "already_accepted"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class ObservationStatus(str, Enum):
    OBSERVED = "observed"
    NOT_MODIFIED = "not_modified"
    FAILED = "failed"


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ObservationContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ObservationContractError(f"{name} must not be empty")
    return value


def _optional_text(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _required_text(name, value)


def _utc_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ObservationContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ObservationContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _optional_utc_datetime(
    name: str,
    value: Optional[datetime],
) -> Optional[datetime]:
    if value is None:
        return None
    return _utc_datetime(name, value)


def _positive_generation(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ObservationContractError(
            "handoff_generation must be a positive integer"
        )
    return value


def _frozen_mapping(name: str, value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ObservationContractError(f"{name} must be a mapping")
    return MappingProxyType(dict(value))


def make_handoff_key(*, target_key: str, handoff_generation: int) -> str:
    target_key = _required_text("target_key", target_key)
    handoff_generation = _positive_generation(handoff_generation)
    payload = f"{target_key}\0{handoff_generation}".encode("utf-8")
    return (
        f"observation:v{OBSERVATION_CONTRACT_VERSION}:"
        f"{hashlib.sha256(payload).hexdigest()}"
    )


@dataclass(frozen=True, slots=True)
class ObservationTarget:
    """Minimal technical target handed from Prospecteur to Observateur."""

    handoff_key: str
    target_key: str
    handoff_generation: int
    locator: str
    kind: str
    requested_at: datetime
    observation_hints: Mapping[str, Any] = field(default_factory=dict)
    contract_version: int = OBSERVATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_key", _required_text("target_key", self.target_key))
        object.__setattr__(
            self,
            "handoff_generation",
            _positive_generation(self.handoff_generation),
        )
        object.__setattr__(self, "locator", _required_text("locator", self.locator))
        object.__setattr__(self, "kind", _required_text("kind", self.kind))
        object.__setattr__(
            self,
            "requested_at",
            _utc_datetime("requested_at", self.requested_at),
        )
        if self.contract_version != OBSERVATION_CONTRACT_VERSION:
            raise ObservationContractError(
                f"unsupported observation contract version {self.contract_version}"
            )
        expected = make_handoff_key(
            target_key=self.target_key,
            handoff_generation=self.handoff_generation,
        )
        if self.handoff_key != expected:
            raise ObservationContractError("handoff_key does not match target/generation")
        object.__setattr__(
            self,
            "observation_hints",
            _frozen_mapping("observation_hints", self.observation_hints),
        )


@dataclass(frozen=True, slots=True)
class ObservationReceipt:
    """Durable-admission acknowledgement returned by the Observateur."""

    handoff_key: str
    target_key: str
    handoff_generation: int
    disposition: ObservationDisposition
    received_at: datetime
    observer_ref: Optional[str] = None
    reason_code: Optional[str] = None
    retry_at: Optional[datetime] = None
    contract_version: int = OBSERVATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_key", _required_text("target_key", self.target_key))
        object.__setattr__(
            self,
            "handoff_generation",
            _positive_generation(self.handoff_generation),
        )
        try:
            disposition = ObservationDisposition(self.disposition)
        except ValueError as exc:
            raise ObservationContractError("invalid observation disposition") from exc
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(
            self,
            "received_at",
            _utc_datetime("received_at", self.received_at),
        )
        object.__setattr__(
            self,
            "observer_ref",
            _optional_text("observer_ref", self.observer_ref),
        )
        object.__setattr__(
            self,
            "reason_code",
            _optional_text("reason_code", self.reason_code),
        )
        object.__setattr__(
            self,
            "retry_at",
            _optional_utc_datetime("retry_at", self.retry_at),
        )
        if self.contract_version != OBSERVATION_CONTRACT_VERSION:
            raise ObservationContractError(
                f"unsupported observation contract version {self.contract_version}"
            )
        expected = make_handoff_key(
            target_key=self.target_key,
            handoff_generation=self.handoff_generation,
        )
        if self.handoff_key != expected:
            raise ObservationContractError("receipt handoff_key is inconsistent")
        if disposition is ObservationDisposition.DEFERRED:
            if self.retry_at is None or self.reason_code is None:
                raise ObservationContractError(
                    "deferred receipt requires retry_at and reason_code"
                )
        elif disposition is ObservationDisposition.REJECTED:
            if self.reason_code is None:
                raise ObservationContractError(
                    "rejected receipt requires reason_code"
                )
            if self.retry_at is not None:
                raise ObservationContractError(
                    "rejected receipt must not carry retry_at"
                )
        elif self.retry_at is not None:
            raise ObservationContractError(
                "accepted receipt must not carry retry_at"
            )


@dataclass(frozen=True, slots=True)
class ObservedReference:
    """Technical reference revealed while observing a source."""

    relation: str
    locator: str
    discovered_at: datetime
    kind: str = "web_url"
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation", _required_text("relation", self.relation))
        object.__setattr__(self, "locator", _required_text("locator", self.locator))
        object.__setattr__(self, "kind", _required_text("kind", self.kind))
        object.__setattr__(
            self,
            "discovered_at",
            _utc_datetime("discovered_at", self.discovered_at),
        )
        object.__setattr__(
            self,
            "attributes",
            _frozen_mapping("attributes", self.attributes),
        )


@dataclass(frozen=True, slots=True)
class ObservationReport:
    """Structure-only feedback from Observateur to Prospecteur.

    Page bodies and extracted semantic facts are deliberately absent. The
    Interpréteur receives content through its own boundary.
    """

    handoff_key: str
    target_key: str
    handoff_generation: int
    observation_ref: str
    status: ObservationStatus
    observed_at: datetime
    requested_locator: str
    final_locator: Optional[str] = None
    response_status: Optional[int] = None
    media_type: Optional[str] = None
    references: Tuple[ObservedReference, ...] = ()
    failure_code: Optional[str] = None
    retry_at: Optional[datetime] = None
    technical_metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: int = OBSERVATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_key", _required_text("target_key", self.target_key))
        object.__setattr__(
            self,
            "handoff_generation",
            _positive_generation(self.handoff_generation),
        )
        object.__setattr__(
            self,
            "observation_ref",
            _required_text("observation_ref", self.observation_ref),
        )
        try:
            status = ObservationStatus(self.status)
        except ValueError as exc:
            raise ObservationContractError("invalid observation status") from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "observed_at",
            _utc_datetime("observed_at", self.observed_at),
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
            "media_type",
            _optional_text("media_type", self.media_type),
        )
        object.__setattr__(
            self,
            "failure_code",
            _optional_text("failure_code", self.failure_code),
        )
        object.__setattr__(
            self,
            "retry_at",
            _optional_utc_datetime("retry_at", self.retry_at),
        )
        if self.response_status is not None:
            try:
                response_status = int(self.response_status)
            except (TypeError, ValueError) as exc:
                raise ObservationContractError(
                    "response_status must be an integer"
                ) from exc
            if not 100 <= response_status <= 599:
                raise ObservationContractError(
                    "response_status must be a valid HTTP status"
                )
            object.__setattr__(self, "response_status", response_status)

        references = tuple(self.references)
        if not all(isinstance(item, ObservedReference) for item in references):
            raise ObservationContractError(
                "references must contain ObservedReference values"
            )
        object.__setattr__(self, "references", references)
        object.__setattr__(
            self,
            "technical_metadata",
            _frozen_mapping("technical_metadata", self.technical_metadata),
        )
        if self.contract_version != OBSERVATION_CONTRACT_VERSION:
            raise ObservationContractError(
                f"unsupported observation contract version {self.contract_version}"
            )
        expected = make_handoff_key(
            target_key=self.target_key,
            handoff_generation=self.handoff_generation,
        )
        if self.handoff_key != expected:
            raise ObservationContractError("report handoff_key is inconsistent")
        if status is ObservationStatus.FAILED:
            if self.failure_code is None:
                raise ObservationContractError(
                    "failed report requires failure_code"
                )
        elif self.failure_code is not None or self.retry_at is not None:
            raise ObservationContractError(
                "successful report must not carry failure_code or retry_at"
            )


def observation_target_from_claim(
    claim: FrontierClaim,
    *,
    requested_at: datetime,
) -> ObservationTarget:
    return ObservationTarget(
        handoff_key=make_handoff_key(
            target_key=claim.target.target_key,
            handoff_generation=claim.handoff_generation,
        ),
        target_key=claim.target.target_key,
        handoff_generation=claim.handoff_generation,
        locator=claim.target.locator,
        kind=claim.target.kind,
        requested_at=requested_at,
        observation_hints=claim.target.observation_hints,
    )
