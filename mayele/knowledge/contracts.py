from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Tuple, Union

from mayele.common.contracts import KnowledgeScope
from mayele.common.errors import MayeleContractError
from mayele.common.fingerprints import semantic_fingerprint
from .semantics import KnowledgeValue


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise MayeleContractError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise MayeleContractError(f"{name} must not be empty")
    return normalized


def _freeze_metadata(metadata: Mapping[str, Any]) -> Tuple[Tuple[str, Any], ...]:
    if not isinstance(metadata, Mapping):
        raise MayeleContractError("metadata must be a mapping")
    frozen: list[tuple[str, Any]] = []
    for key, value in sorted(metadata.items()):
        if not isinstance(key, str) or not key.strip():
            raise MayeleContractError("metadata keys must be non-empty strings")
        if not (
            isinstance(value, (str, int, float, bool))
            or value is None
            or isinstance(value, KnowledgeValue)
        ):
            raise MayeleContractError(
                "metadata values must be scalar JSON values or KnowledgeValue"
            )
        frozen.append((key.strip(), value))
    return tuple(frozen)


class PropositionKind(str, Enum):
    REALITY_EXISTS = "REALITY_EXISTS"
    PROPERTY_HOLDS = "PROPERTY_HOLDS"
    RELATION_HOLDS = "RELATION_HOLDS"
    CONDITION_APPLIES = "CONDITION_APPLIES"


class SupportDisposition(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    QUALIFIES = "QUALIFIES"


class AssessmentStatus(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTORY = "CONTRADICTORY"
    UNRESOLVED = "UNRESOLVED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class TemporalValidity:
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    def __post_init__(self) -> None:
        for name, value in (
            ("valid_from", self.valid_from),
            ("valid_until", self.valid_until),
        ):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() is None
            ):
                raise MayeleContractError(f"{name} must be timezone-aware")
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_from >= self.valid_until
        ):
            raise MayeleContractError("valid_from must be before valid_until")

    def to_payload(self) -> dict[str, str | None]:
        return {
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
        }


@dataclass(frozen=True, slots=True)
class Reality:
    """A Mayele identity independent from names, sources and contextual roles."""

    reality_ref: str
    label: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "reality_ref", _required_text("reality_ref", self.reality_ref)
        )
        if self.label is not None:
            object.__setattr__(self, "label", _required_text("label", self.label))


@dataclass(frozen=True, slots=True)
class Property:
    reality_ref: str
    attribute: str
    value: Any

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "reality_ref", _required_text("reality_ref", self.reality_ref)
        )
        object.__setattr__(
            self, "attribute", _required_text("attribute", self.attribute)
        )
        if not (
            isinstance(self.value, (str, int, float, bool))
            or self.value is None
            or isinstance(self.value, KnowledgeValue)
        ):
            raise MayeleContractError(
                "property value must be scalar JSON, None or KnowledgeValue"
            )


@dataclass(frozen=True, slots=True)
class RelationParticipant:
    role: str
    reality_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _required_text("role", self.role))
        object.__setattr__(
            self, "reality_ref", _required_text("reality_ref", self.reality_ref)
        )


@dataclass(frozen=True, slots=True)
class Relation:
    predicate: str
    participants: Tuple[RelationParticipant, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "predicate", _required_text("predicate", self.predicate)
        )
        participants = tuple(self.participants)
        if len(participants) < 2 or not all(
            isinstance(item, RelationParticipant) for item in participants
        ):
            raise MayeleContractError(
                "relation requires at least two typed participants"
            )
        object.__setattr__(self, "participants", participants)


@dataclass(frozen=True, slots=True)
class Condition:
    expression: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "expression", _required_text("expression", self.expression)
        )


SemanticTarget = Union[Reality, Property, Relation, Condition]


@dataclass(frozen=True, slots=True)
class Proposition:
    kind: PropositionKind
    target: SemanticTarget
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)
    validity: Optional[TemporalValidity] = None

    def __post_init__(self) -> None:
        try:
            kind = PropositionKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid proposition kind") from exc
        object.__setattr__(self, "kind", kind)

        expected = {
            PropositionKind.REALITY_EXISTS: Reality,
            PropositionKind.PROPERTY_HOLDS: Property,
            PropositionKind.RELATION_HOLDS: Relation,
            PropositionKind.CONDITION_APPLIES: Condition,
        }[kind]
        if not isinstance(self.target, expected):
            raise MayeleContractError(
                f"{kind.value} requires target {expected.__name__}"
            )
        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")
        if self.validity is not None and not isinstance(
            self.validity, TemporalValidity
        ):
            raise MayeleContractError("validity must be TemporalValidity or None")

    def semantic_payload(self) -> dict[str, Any]:
        target: dict[str, Any]
        if isinstance(self.target, Reality):
            target = {
                "type": "Reality",
                "reality_ref": self.target.reality_ref,
            }
        elif isinstance(self.target, Property):
            value = (
                self.target.value.value
                if isinstance(self.target.value, KnowledgeValue)
                else self.target.value
            )
            target = {
                "type": "Property",
                "reality_ref": self.target.reality_ref,
                "attribute": self.target.attribute,
                "value": value,
            }
        elif isinstance(self.target, Relation):
            target = {
                "type": "Relation",
                "predicate": self.target.predicate,
                "participants": [
                    {"role": item.role, "reality_ref": item.reality_ref}
                    for item in self.target.participants
                ],
            }
        else:
            target = {
                "type": "Condition",
                "expression": self.target.expression,
            }

        return {
            "kind": self.kind.value,
            "target": target,
            "scope": self.scope.to_payload(),
            "validity": self.validity.to_payload() if self.validity else None,
        }

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(self.semantic_payload())


@dataclass(frozen=True, slots=True)
class KnowledgeSupport:
    proposition_fingerprint: str
    support_ref: str
    disposition: SupportDisposition
    metadata: Tuple[Tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "proposition_fingerprint",
            _required_text(
                "proposition_fingerprint", self.proposition_fingerprint
            ),
        )
        object.__setattr__(
            self, "support_ref", _required_text("support_ref", self.support_ref)
        )
        try:
            disposition = SupportDisposition(self.disposition)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid support disposition") from exc
        object.__setattr__(self, "disposition", disposition)
        if isinstance(self.metadata, Mapping):
            object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        else:
            metadata = tuple(self.metadata)
            _freeze_metadata(dict(metadata))
            object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class PropositionAssessment:
    proposition_fingerprint: str
    status: AssessmentStatus
    assessed_at: datetime
    metadata: Tuple[Tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "proposition_fingerprint",
            _required_text(
                "proposition_fingerprint", self.proposition_fingerprint
            ),
        )
        try:
            status = AssessmentStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid assessment status") from exc
        object.__setattr__(self, "status", status)
        if (
            self.assessed_at.tzinfo is None
            or self.assessed_at.utcoffset() is None
        ):
            raise MayeleContractError("assessed_at must be timezone-aware")
        if isinstance(self.metadata, Mapping):
            object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        else:
            metadata = tuple(self.metadata)
            _freeze_metadata(dict(metadata))
            object.__setattr__(self, "metadata", metadata)
