from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from .errors import ProspectorContractError

CONTRACT_VERSION = 1


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ProspectorContractError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ProspectorContractError(f"{name} must not be empty")
    return normalized


def _optional_text(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _required_text(name, value)


def _utc_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ProspectorContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProspectorContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _frozen_mapping(name: str, value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProspectorContractError(f"{name} must be a mapping")
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class ProspectingEvidence:
    """Provenance explaining why a candidate entered prospecting."""

    method: str
    discovered_at: datetime
    source_target_key: Optional[str] = None
    source_observation_ref: Optional[str] = None
    provider: Optional[str] = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _required_text("method", self.method))
        object.__setattr__(
            self,
            "discovered_at",
            _utc_datetime("discovered_at", self.discovered_at),
        )
        object.__setattr__(
            self,
            "source_target_key",
            _optional_text("source_target_key", self.source_target_key),
        )
        object.__setattr__(
            self,
            "source_observation_ref",
            _optional_text("source_observation_ref", self.source_observation_ref),
        )
        object.__setattr__(self, "provider", _optional_text("provider", self.provider))
        object.__setattr__(
            self,
            "attributes",
            _frozen_mapping("attributes", self.attributes),
        )


@dataclass(frozen=True, slots=True)
class ProspectingCandidate:
    """Unresolved resource locator produced by a prospecting mechanism."""

    locator: str
    kind: str
    evidence: Tuple[ProspectingEvidence, ...]
    policy_context: Mapping[str, Any] = field(default_factory=dict)
    observation_hints: Mapping[str, Any] = field(default_factory=dict)
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "locator", _required_text("locator", self.locator))
        object.__setattr__(self, "kind", _required_text("kind", self.kind))
        if not isinstance(self.contract_version, int) or self.contract_version < 1:
            raise ProspectorContractError("contract_version must be a positive integer")
        evidence = tuple(self.evidence)
        if not evidence:
            raise ProspectorContractError("evidence must contain at least one item")
        if not all(isinstance(item, ProspectingEvidence) for item in evidence):
            raise ProspectorContractError("evidence must contain ProspectingEvidence values")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(
            self,
            "policy_context",
            _frozen_mapping("policy_context", self.policy_context),
        )
        object.__setattr__(
            self,
            "observation_hints",
            _frozen_mapping("observation_hints", self.observation_hints),
        )


@dataclass(frozen=True, slots=True)
class ProspectingTarget:
    """Canonical target identity admitted to the Makolo prospecting frontier."""

    target_key: str
    locator: str
    kind: str
    first_discovered_at: datetime
    evidence: Tuple[ProspectingEvidence, ...]
    policy_context: Mapping[str, Any] = field(default_factory=dict)
    observation_hints: Mapping[str, Any] = field(default_factory=dict)
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "target_key",
            _required_text("target_key", self.target_key),
        )
        object.__setattr__(self, "locator", _required_text("locator", self.locator))
        object.__setattr__(self, "kind", _required_text("kind", self.kind))
        object.__setattr__(
            self,
            "first_discovered_at",
            _utc_datetime("first_discovered_at", self.first_discovered_at),
        )
        if not isinstance(self.contract_version, int) or self.contract_version < 1:
            raise ProspectorContractError("contract_version must be a positive integer")
        evidence = tuple(self.evidence)
        if not evidence:
            raise ProspectorContractError("evidence must contain at least one item")
        if not all(isinstance(item, ProspectingEvidence) for item in evidence):
            raise ProspectorContractError("evidence must contain ProspectingEvidence values")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(
            self,
            "policy_context",
            _frozen_mapping("policy_context", self.policy_context),
        )
        object.__setattr__(
            self,
            "observation_hints",
            _frozen_mapping("observation_hints", self.observation_hints),
        )
