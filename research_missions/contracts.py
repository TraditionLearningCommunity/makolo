from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple


RESEARCH_MISSION_CONTRACT_VERSION = 1


class ResearchMissionContractError(ValueError):
    """Raised when an internal research-mission contract is invalid."""


class ResearchFamily(str, Enum):
    POSSIBILITY = "POSSIBILITY"
    REQUIREMENT = "REQUIREMENT"
    QUALIFICATION = "QUALIFICATION"
    ACTOR = "ACTOR"
    SPATIOTEMPORAL = "SPATIOTEMPORAL"
    PROCEDURE = "PROCEDURE"
    ECONOMIC = "ECONOMIC"
    REFERENCE = "REFERENCE"


class ResearchOriginKind(str, Enum):
    INITIAL = "initial"
    WATCH = "watch"
    CANONICAL_REALITY = "canonical_reality"
    REQUIREMENT = "requirement"
    UNRESOLVED_DEPENDENCY = "unresolved_dependency"
    PREVIOUS_PROCESSING = "previous_processing"


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ResearchMissionContractError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise ResearchMissionContractError(f"{name} must not be empty")
    return normalized


def _optional_text(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _required_text(name, value)


def _text_tuple(name: str, values, *, required: bool = False) -> Tuple[str, ...]:
    normalized = []
    for value in tuple(values or ()):
        text = _required_text(name, value)
        if text not in normalized:
            normalized.append(text)
    if required and not normalized:
        raise ResearchMissionContractError(
            f"{name} must contain at least one value"
        )
    return tuple(normalized)


def _freeze_json(value):
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def thaw_json(value):
    """Return JSON-native mutable containers at persistence/projection boundaries."""

    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def _frozen_json_mapping(name: str, value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResearchMissionContractError(f"{name} must be a mapping")
    data = dict(value)
    if any(not isinstance(key, str) for key in data):
        raise ResearchMissionContractError(f"{name} keys must be strings")
    try:
        encoded = json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ResearchMissionContractError(
            f"{name} must be JSON-serializable"
        ) from exc
    return _freeze_json(json.loads(encoded))


def _identity_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return " ".join(value.split()).casefold()


def _fingerprint(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _identity_payload(
    *,
    primary_family: ResearchFamily,
    subject: str,
    questions: Tuple[str, ...],
    unknowns: Tuple[str, ...],
    scope: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        "contract_version": RESEARCH_MISSION_CONTRACT_VERSION,
        "primary_family": primary_family.value,
        "subject": _identity_text(subject),
        "questions": sorted({_identity_text(value) for value in questions}),
        "unknowns": sorted({_identity_text(value) for value in unknowns}),
        "scope": thaw_json(scope),
    }


@dataclass(frozen=True, slots=True)
class ResearchOrigin:
    """Provenance explaining why a bounded research need was proposed."""

    kind: ResearchOriginKind
    source_ref: Optional[str] = None
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            kind = ResearchOriginKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise ResearchMissionContractError(
                "invalid research origin kind"
            ) from exc
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "source_ref",
            _optional_text("source_ref", self.source_ref),
        )
        object.__setattr__(
            self,
            "context",
            _frozen_json_mapping("origin.context", self.context),
        )

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_payload())

    def to_payload(self) -> Mapping[str, Any]:
        return {
            "kind": self.kind.value,
            "source_ref": self.source_ref,
            "context": thaw_json(self.context),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ResearchOrigin":
        if not isinstance(payload, Mapping):
            raise ResearchMissionContractError(
                "origin payload must be a mapping"
            )
        return cls(
            kind=payload.get("kind"),
            source_ref=payload.get("source_ref"),
            context=payload.get("context") or {},
        )


@dataclass(frozen=True, slots=True)
class ResearchMission:
    """Bounded internal intent to resolve a Makolo knowledge need.

    It is neither a business truth nor an execution task. Logical identity is
    deliberately independent from provenance, priority and execution budgets.
    """

    primary_family: ResearchFamily
    subject: str
    questions: Tuple[str, ...]
    known_context: Mapping[str, Any] = field(default_factory=dict)
    unknowns: Tuple[str, ...] = ()
    origins: Tuple[ResearchOrigin, ...] = ()
    reasons: Tuple[str, ...] = ()
    priority: Optional[int] = None
    scope: Mapping[str, Any] = field(default_factory=dict)
    limits: Mapping[str, Any] = field(default_factory=dict)
    contract_version: int = RESEARCH_MISSION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != RESEARCH_MISSION_CONTRACT_VERSION:
            raise ResearchMissionContractError(
                "unsupported research mission contract version "
                f"{self.contract_version}"
            )
        try:
            family = ResearchFamily(self.primary_family)
        except (TypeError, ValueError) as exc:
            raise ResearchMissionContractError(
                "invalid research mission family"
            ) from exc
        object.__setattr__(self, "primary_family", family)
        object.__setattr__(
            self,
            "subject",
            _required_text("subject", self.subject),
        )
        object.__setattr__(
            self,
            "questions",
            _text_tuple("questions", self.questions, required=True),
        )
        object.__setattr__(
            self,
            "unknowns",
            _text_tuple("unknowns", self.unknowns),
        )
        object.__setattr__(
            self,
            "known_context",
            _frozen_json_mapping("known_context", self.known_context),
        )
        object.__setattr__(
            self,
            "scope",
            _frozen_json_mapping("scope", self.scope),
        )
        object.__setattr__(
            self,
            "limits",
            _frozen_json_mapping("limits", self.limits),
        )

        origins = tuple(self.origins)
        if not origins or not all(
            isinstance(value, ResearchOrigin) for value in origins
        ):
            raise ResearchMissionContractError(
                "origins must contain at least one ResearchOrigin"
            )
        unique_origins = []
        seen_origin_keys = set()
        for origin in origins:
            if origin.fingerprint not in seen_origin_keys:
                unique_origins.append(origin)
                seen_origin_keys.add(origin.fingerprint)
        object.__setattr__(self, "origins", tuple(unique_origins))
        object.__setattr__(
            self,
            "reasons",
            _text_tuple("reasons", self.reasons, required=True),
        )

        if self.priority is not None and (
            not isinstance(self.priority, int)
            or isinstance(self.priority, bool)
            or not 0 <= self.priority <= 1000
        ):
            raise ResearchMissionContractError(
                "priority must be an integer between 0 and 1000 or None"
            )

    @property
    def fingerprint(self) -> str:
        return _fingerprint(
            _identity_payload(
                primary_family=self.primary_family,
                subject=self.subject,
                questions=self.questions,
                unknowns=self.unknowns,
                scope=self.scope,
            )
        )

    @property
    def mission_ref(self) -> str:
        return f"research-mission:v{self.contract_version}:{self.fingerprint}"

    @property
    def mission_key(self) -> str:
        return self.mission_ref

    def with_provenance(
        self,
        *,
        origin: ResearchOrigin,
        reason: str,
    ) -> "ResearchMission":
        if not isinstance(origin, ResearchOrigin):
            raise ResearchMissionContractError(
                "origin must be a ResearchOrigin"
            )
        reason = _required_text("reason", reason)
        origins = self.origins
        if all(
            value.fingerprint != origin.fingerprint
            for value in origins
        ):
            origins = origins + (origin,)
        reasons = (
            self.reasons
            if reason in self.reasons
            else self.reasons + (reason,)
        )
        return replace(self, origins=origins, reasons=reasons)

    def to_provenance_payload(self) -> Mapping[str, Any]:
        return {
            "contract_version": self.contract_version,
            "mission_ref": self.mission_ref,
            "mission_fingerprint": self.fingerprint,
            "primary_family": self.primary_family.value,
            "subject": self.subject,
            "questions": list(self.questions),
            "known_context": thaw_json(self.known_context),
            "unknowns": list(self.unknowns),
            "origins": [
                origin.to_payload() for origin in self.origins
            ],
            "reasons": list(self.reasons),
            "priority": self.priority,
            "scope": thaw_json(self.scope),
            "limits": thaw_json(self.limits),
        }

    @classmethod
    def from_provenance_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "ResearchMission":
        if not isinstance(payload, Mapping):
            raise ResearchMissionContractError(
                "research mission payload must be a mapping"
            )
        mission = cls(
            contract_version=payload.get(
                "contract_version",
                RESEARCH_MISSION_CONTRACT_VERSION,
            ),
            primary_family=payload.get("primary_family"),
            subject=payload.get("subject"),
            questions=tuple(payload.get("questions") or ()),
            known_context=payload.get("known_context") or {},
            unknowns=tuple(payload.get("unknowns") or ()),
            origins=tuple(
                ResearchOrigin.from_payload(value)
                for value in tuple(payload.get("origins") or ())
            ),
            reasons=tuple(payload.get("reasons") or ()),
            priority=payload.get("priority"),
            scope=payload.get("scope") or {},
            limits=payload.get("limits") or {},
        )
        stored_fingerprint = payload.get("mission_fingerprint")
        if (
            stored_fingerprint is not None
            and stored_fingerprint != mission.fingerprint
        ):
            raise ResearchMissionContractError(
                "research mission fingerprint mismatch"
            )
        stored_ref = payload.get("mission_ref")
        if stored_ref is not None and stored_ref != mission.mission_ref:
            raise ResearchMissionContractError(
                "research mission ref mismatch"
            )
        return mission


@dataclass(frozen=True, slots=True)
class ResearchMissionCandidate:
    """Suggested research need; construction never schedules or executes it."""

    primary_family: ResearchFamily
    subject: str
    questions: Tuple[str, ...]
    origin: ResearchOrigin
    reason: str
    known_context: Mapping[str, Any] = field(default_factory=dict)
    unknowns: Tuple[str, ...] = ()
    priority: Optional[int] = None
    scope: Mapping[str, Any] = field(default_factory=dict)
    limits: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        mission = self.to_mission()
        object.__setattr__(
            self, "primary_family", mission.primary_family
        )
        object.__setattr__(self, "subject", mission.subject)
        object.__setattr__(self, "questions", mission.questions)
        object.__setattr__(
            self, "known_context", mission.known_context
        )
        object.__setattr__(self, "unknowns", mission.unknowns)
        object.__setattr__(self, "origin", mission.origins[0])
        object.__setattr__(self, "reason", mission.reasons[0])
        object.__setattr__(self, "priority", mission.priority)
        object.__setattr__(self, "scope", mission.scope)
        object.__setattr__(self, "limits", mission.limits)

    def to_mission(self) -> ResearchMission:
        """Explicit admission primitive; callers still decide whether to execute."""

        return ResearchMission(
            primary_family=self.primary_family,
            subject=self.subject,
            questions=self.questions,
            known_context=self.known_context,
            unknowns=self.unknowns,
            origins=(self.origin,),
            reasons=(self.reason,),
            priority=self.priority,
            scope=self.scope,
            limits=self.limits,
        )

    @property
    def fingerprint(self) -> str:
        return self.to_mission().fingerprint

    @property
    def mission_ref(self) -> str:
        return self.to_mission().mission_ref


@dataclass(frozen=True, slots=True)
class ResearchContext:
    """Minimal read-only mission projection intended for a future Actor 3."""

    mission_ref: str
    mission_fingerprint: str
    primary_family: ResearchFamily
    subject: str
    questions: Tuple[str, ...]
    known_context: Mapping[str, Any]
    unknowns: Tuple[str, ...]
    origins: Tuple[ResearchOrigin, ...]
    reasons: Tuple[str, ...]
    scope: Mapping[str, Any]

    @classmethod
    def from_mission(
        cls,
        mission: ResearchMission,
    ) -> "ResearchContext":
        return cls(
            mission_ref=mission.mission_ref,
            mission_fingerprint=mission.fingerprint,
            primary_family=mission.primary_family,
            subject=mission.subject,
            questions=mission.questions,
            known_context=mission.known_context,
            unknowns=mission.unknowns,
            origins=mission.origins,
            reasons=mission.reasons,
            scope=mission.scope,
        )

    def with_merged_provenance(
        self,
        other: "ResearchContext",
    ) -> "ResearchContext":
        if not isinstance(other, ResearchContext):
            raise ResearchMissionContractError(
                "other must be a ResearchContext"
            )
        if (
            self.mission_ref != other.mission_ref
            or self.mission_fingerprint
            != other.mission_fingerprint
        ):
            raise ResearchMissionContractError(
                "cannot merge provenance for different logical missions"
            )
        origins = list(self.origins)
        seen = {origin.fingerprint for origin in origins}
        for origin in other.origins:
            if origin.fingerprint not in seen:
                origins.append(origin)
                seen.add(origin.fingerprint)
        reasons = list(self.reasons)
        for reason in other.reasons:
            if reason not in reasons:
                reasons.append(reason)
        return replace(
            self,
            origins=tuple(origins),
            reasons=tuple(reasons),
        )
