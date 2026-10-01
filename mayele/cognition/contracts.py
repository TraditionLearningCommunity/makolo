from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Tuple

from mayele.common.contracts import KnowledgeScope, ScopeVisibility
from mayele.common.errors import MayeleContractError
from mayele.common.fingerprints import semantic_fingerprint
from mayele.knowledge import KnowledgeValue
from mayele.observation import Mention, ObservedStatement


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise MayeleContractError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise MayeleContractError(f"{name} must not be empty")
    return normalized


def _optional_text(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _required_text(name, value)


def _aware_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise MayeleContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise MayeleContractError(f"{name} must be timezone-aware")
    return value


def _scope_rank(scope: KnowledgeScope) -> int:
    return {
        ScopeVisibility.PUBLIC: 0,
        ScopeVisibility.RESTRICTED: 1,
        ScopeVisibility.PRIVATE: 2,
    }[scope.visibility]


def _derived_scope(
    parent: KnowledgeScope, child: Optional[KnowledgeScope]
) -> KnowledgeScope:
    if child is None:
        return parent
    if not isinstance(child, KnowledgeScope):
        raise MayeleContractError("scope must be KnowledgeScope")
    if _scope_rank(child) < _scope_rank(parent):
        raise MayeleContractError("knowledge scope cannot be widened implicitly")
    if parent.context_ref is not None and child.context_ref != parent.context_ref:
        raise MayeleContractError(
            "derived non-public knowledge must preserve its parent context_ref"
        )
    return child


def _semantic_value(value: Any) -> Any:
    if isinstance(value, KnowledgeValue):
        return value.value
    return value


class InterpretationMode(str, Enum):
    EXPLICIT = "EXPLICIT"
    NORMALIZED = "NORMALIZED"
    INFERRED = "INFERRED"


class InterpretationTransformation(str, Enum):
    TRANSLATION = "TRANSLATION"


class ReferentKind(str, Enum):
    MENTION = "MENTION"
    REALITY_CANDIDATE = "REALITY_CANDIDATE"
    REALITY = "REALITY"


class CandidateStatus(str, Enum):
    PROPOSED = "PROPOSED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class InterpretationReferent:
    """Typed reference used before identity resolution is complete."""

    kind: ReferentKind
    ref: str

    def __post_init__(self) -> None:
        try:
            kind = ReferentKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid referent kind") from exc
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "ref", _required_text("ref", self.ref))

    def to_payload(self) -> dict[str, str]:
        return {"kind": self.kind.value, "ref": self.ref}


@dataclass(frozen=True, slots=True)
class Interpretation:
    """Technical lineage for what Mayele interprets from one observed statement."""

    interpretation_ref: str
    statement: ObservedStatement
    interpreted_at: datetime
    mode: InterpretationMode
    mentions: Tuple[Mention, ...] = ()
    method_ref: Optional[str] = None
    method_version: Optional[str] = None
    transformation: Optional[InterpretationTransformation] = None
    scope: Optional[KnowledgeScope] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "interpretation_ref",
            _required_text("interpretation_ref", self.interpretation_ref),
        )
        if not isinstance(self.statement, ObservedStatement):
            raise MayeleContractError("statement must be ObservedStatement")
        object.__setattr__(
            self,
            "interpreted_at",
            _aware_datetime("interpreted_at", self.interpreted_at),
        )
        try:
            mode = InterpretationMode(self.mode)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid interpretation mode") from exc
        object.__setattr__(self, "mode", mode)

        mentions = tuple(self.mentions)
        if not all(isinstance(item, Mention) for item in mentions):
            raise MayeleContractError("mentions must contain Mention values")
        if len({item.mention_ref for item in mentions}) != len(mentions):
            raise MayeleContractError("interpretation mentions must be unique")
        for mention in mentions:
            if mention.statement.statement_ref != self.statement.statement_ref:
                raise MayeleContractError(
                    "interpretation mentions must belong to the interpreted statement"
                )
        object.__setattr__(self, "mentions", mentions)

        object.__setattr__(
            self, "method_ref", _optional_text("method_ref", self.method_ref)
        )
        object.__setattr__(
            self,
            "method_version",
            _optional_text("method_version", self.method_version),
        )
        if self.method_version is not None and self.method_ref is None:
            raise MayeleContractError("method_version requires method_ref")

        if self.transformation is not None:
            try:
                transformation = InterpretationTransformation(self.transformation)
            except (TypeError, ValueError) as exc:
                raise MayeleContractError(
                    "invalid interpretation transformation"
                ) from exc
            object.__setattr__(self, "transformation", transformation)

        object.__setattr__(
            self, "scope", _derived_scope(self.statement.scope, self.scope)
        )

    @property
    def execution_fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "interpretation_ref": self.interpretation_ref,
                "statement_ref": self.statement.statement_ref,
                "mention_refs": [item.mention_ref for item in self.mentions],
                "interpreted_at": self.interpreted_at,
                "mode": self.mode.value,
                "method_ref": self.method_ref,
                "method_version": self.method_version,
                "transformation": (
                    self.transformation.value if self.transformation else None
                ),
                "scope": self.scope.to_payload(),
            }
        )


@dataclass(frozen=True, slots=True)
class RealityCandidate:
    candidate_ref: str
    interpretation: Interpretation
    source_referent: Optional[InterpretationReferent] = None
    label: Optional[str] = None
    status: CandidateStatus = CandidateStatus.PROPOSED
    scope: Optional[KnowledgeScope] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_ref", _required_text("candidate_ref", self.candidate_ref)
        )
        if not isinstance(self.interpretation, Interpretation):
            raise MayeleContractError("interpretation must be Interpretation")
        if self.source_referent is not None and not isinstance(
            self.source_referent, InterpretationReferent
        ):
            raise MayeleContractError(
                "source_referent must be InterpretationReferent or None"
            )
        object.__setattr__(self, "label", _optional_text("label", self.label))
        try:
            status = CandidateStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid candidate status") from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self, "scope", _derived_scope(self.interpretation.scope, self.scope)
        )

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "type": "RealityCandidate",
                "source_referent": (
                    self.source_referent.to_payload()
                    if self.source_referent is not None
                    else None
                ),
                "label": self.label,
                "scope": self.scope.to_payload(),
            }
        )


@dataclass(frozen=True, slots=True)
class PropertyCandidate:
    candidate_ref: str
    interpretation: Interpretation
    subject: InterpretationReferent
    attribute: str
    value: Any
    status: CandidateStatus = CandidateStatus.PROPOSED
    scope: Optional[KnowledgeScope] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_ref", _required_text("candidate_ref", self.candidate_ref)
        )
        if not isinstance(self.interpretation, Interpretation):
            raise MayeleContractError("interpretation must be Interpretation")
        if not isinstance(self.subject, InterpretationReferent):
            raise MayeleContractError("subject must be InterpretationReferent")
        object.__setattr__(
            self, "attribute", _required_text("attribute", self.attribute)
        )
        if self.value is None:
            raise MayeleContractError(
                "property candidate value must be explicit; use KnowledgeValue.UNKNOWN "
                "only when the source explicitly supports unknown"
            )
        if not (
            isinstance(self.value, (str, int, float, bool))
            or isinstance(self.value, KnowledgeValue)
        ):
            raise MayeleContractError(
                "property candidate value must be scalar JSON or KnowledgeValue"
            )
        try:
            status = CandidateStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid candidate status") from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self, "scope", _derived_scope(self.interpretation.scope, self.scope)
        )

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "type": "PropertyCandidate",
                "subject": self.subject.to_payload(),
                "attribute": self.attribute,
                "value": _semantic_value(self.value),
                "scope": self.scope.to_payload(),
            }
        )


@dataclass(frozen=True, slots=True)
class RelationCandidateParticipant:
    role: str
    referent: InterpretationReferent

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _required_text("role", self.role))
        if not isinstance(self.referent, InterpretationReferent):
            raise MayeleContractError("referent must be InterpretationReferent")

    def to_payload(self) -> dict[str, Any]:
        return {"role": self.role, "referent": self.referent.to_payload()}


@dataclass(frozen=True, slots=True)
class RelationCandidate:
    candidate_ref: str
    interpretation: Interpretation
    predicate: str
    participants: Tuple[RelationCandidateParticipant, ...]
    status: CandidateStatus = CandidateStatus.PROPOSED
    scope: Optional[KnowledgeScope] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_ref", _required_text("candidate_ref", self.candidate_ref)
        )
        if not isinstance(self.interpretation, Interpretation):
            raise MayeleContractError("interpretation must be Interpretation")
        object.__setattr__(
            self, "predicate", _required_text("predicate", self.predicate)
        )
        participants = tuple(self.participants)
        if len(participants) < 2 or not all(
            isinstance(item, RelationCandidateParticipant) for item in participants
        ):
            raise MayeleContractError(
                "relation candidate requires at least two typed participants"
            )
        participant_keys = {
            (item.role, item.referent.kind.value, item.referent.ref)
            for item in participants
        }
        if len(participant_keys) != len(participants):
            raise MayeleContractError(
                "relation candidate participants must not contain exact duplicates"
            )
        object.__setattr__(self, "participants", participants)
        try:
            status = CandidateStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid candidate status") from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self, "scope", _derived_scope(self.interpretation.scope, self.scope)
        )

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "type": "RelationCandidate",
                "predicate": self.predicate,
                "participants": [item.to_payload() for item in self.participants],
                "scope": self.scope.to_payload(),
            }
        )


@dataclass(frozen=True, slots=True)
class ConditionCandidate:
    candidate_ref: str
    interpretation: Interpretation
    expression: str
    referents: Tuple[InterpretationReferent, ...] = ()
    status: CandidateStatus = CandidateStatus.PROPOSED
    scope: Optional[KnowledgeScope] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_ref", _required_text("candidate_ref", self.candidate_ref)
        )
        if not isinstance(self.interpretation, Interpretation):
            raise MayeleContractError("interpretation must be Interpretation")
        object.__setattr__(
            self, "expression", _required_text("expression", self.expression)
        )
        referents = tuple(self.referents)
        if not all(isinstance(item, InterpretationReferent) for item in referents):
            raise MayeleContractError(
                "condition candidate referents must be InterpretationReferent values"
            )
        referent_keys = {(item.kind.value, item.ref) for item in referents}
        if len(referent_keys) != len(referents):
            raise MayeleContractError(
                "condition candidate referents must not contain duplicates"
            )
        object.__setattr__(self, "referents", referents)
        try:
            status = CandidateStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid candidate status") from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self, "scope", _derived_scope(self.interpretation.scope, self.scope)
        )

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "type": "ConditionCandidate",
                "expression": self.expression,
                "referents": [item.to_payload() for item in self.referents],
                "scope": self.scope.to_payload(),
            }
        )


WorldCandidate = (
    RealityCandidate | PropertyCandidate | RelationCandidate | ConditionCandidate
)
