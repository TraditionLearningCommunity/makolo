from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

from mayele.cognition import (
    CandidateStatus,
    ConditionCandidate,
    InterpretationReferent,
    PropertyCandidate,
    RealityCandidate,
    ReferentKind,
    RelationCandidate,
    WorldCandidate,
)
from mayele.common.contracts import KnowledgeScope, ScopeVisibility
from mayele.common.errors import MayeleContractError
from mayele.identity import IdentityResolution, IdentityResolutionStatus
from mayele.observation import ObservedStatement

from .contracts import (
    Condition,
    KnowledgeSupport,
    Property,
    Proposition,
    PropositionKind,
    Relation,
    RelationParticipant,
    SupportDisposition,
    TemporalValidity,
)


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


def _combine_scopes(*scopes: KnowledgeScope) -> KnowledgeScope:
    if not scopes:
        return KnowledgeScope()
    for scope in scopes:
        if not isinstance(scope, KnowledgeScope):
            raise MayeleContractError("all construction scopes must be KnowledgeScope")

    non_public_contexts = {
        scope.context_ref
        for scope in scopes
        if scope.visibility is not ScopeVisibility.PUBLIC
    }
    if len(non_public_contexts) > 1:
        raise MayeleContractError(
            "incompatible non-public scopes cannot be merged implicitly"
        )

    visibility = max(scopes, key=_scope_rank).visibility
    if visibility is ScopeVisibility.PUBLIC:
        return KnowledgeScope()
    return KnowledgeScope(visibility, next(iter(non_public_contexts)))


def _resolution_for(
    referent: InterpretationReferent,
    resolutions: Tuple[IdentityResolution, ...],
) -> IdentityResolution:
    matches = tuple(item for item in resolutions if item.referent == referent)
    if not matches:
        raise MayeleContractError(
            f"identity resolution required for {referent.kind.value}:{referent.ref}"
        )
    if len(matches) != 1:
        raise MayeleContractError(
            f"exactly one identity resolution is required for {referent.kind.value}:{referent.ref}"
        )
    resolution = matches[0]
    if resolution.status is IdentityResolutionStatus.UNRESOLVED:
        raise MayeleContractError("UNRESOLVED referent cannot be promoted to Reality")
    if resolution.reality is None:
        raise MayeleContractError("resolved referent must select a Reality")
    return resolution


def _reality_ref_for(
    referent: InterpretationReferent,
    resolutions: Tuple[IdentityResolution, ...],
    used: list[IdentityResolution],
) -> str:
    if referent.kind is ReferentKind.REALITY:
        return referent.ref
    resolution = _resolution_for(referent, resolutions)
    if resolution not in used:
        used.append(resolution)
    return resolution.reality.reality_ref


@dataclass(frozen=True, slots=True)
class PropositionConstruction:
    """Lineage explaining how one MY3 candidate produced one MY1 Proposition."""

    candidate_ref: str
    candidate_fingerprint: str
    proposition: Proposition
    constructed_at: datetime
    source_referents: Tuple[InterpretationReferent, ...] = ()
    identity_resolutions: Tuple[IdentityResolution, ...] = ()
    scope: Optional[KnowledgeScope] = None
    construction_rule_ref: Optional[str] = None
    construction_rule_version: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_ref", _required_text("candidate_ref", self.candidate_ref)
        )
        object.__setattr__(
            self,
            "candidate_fingerprint",
            _required_text("candidate_fingerprint", self.candidate_fingerprint),
        )
        if not isinstance(self.proposition, Proposition):
            raise MayeleContractError("proposition must be Proposition")
        object.__setattr__(
            self, "constructed_at", _aware_datetime("constructed_at", self.constructed_at)
        )

        source_referents = tuple(self.source_referents)
        if not all(
            isinstance(item, InterpretationReferent) for item in source_referents
        ):
            raise MayeleContractError(
                "source_referents must contain InterpretationReferent values"
            )
        source_keys = {(item.kind.value, item.ref) for item in source_referents}
        if len(source_keys) != len(source_referents):
            raise MayeleContractError("source referents must be unique")
        object.__setattr__(self, "source_referents", source_referents)

        resolutions = tuple(self.identity_resolutions)
        if not all(isinstance(item, IdentityResolution) for item in resolutions):
            raise MayeleContractError(
                "identity_resolutions must contain IdentityResolution values"
            )
        refs = [item.resolution_ref for item in resolutions]
        if len(set(refs)) != len(refs):
            raise MayeleContractError("identity resolutions must be unique")
        object.__setattr__(self, "identity_resolutions", resolutions)

        scope = self.proposition.scope if self.scope is None else self.scope
        if not isinstance(scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")
        if scope != self.proposition.scope:
            raise MayeleContractError(
                "construction scope must equal the produced Proposition scope"
            )
        object.__setattr__(self, "scope", scope)

        object.__setattr__(
            self,
            "construction_rule_ref",
            _optional_text("construction_rule_ref", self.construction_rule_ref),
        )
        object.__setattr__(
            self,
            "construction_rule_version",
            _optional_text(
                "construction_rule_version", self.construction_rule_version
            ),
        )
        if (
            self.construction_rule_version is not None
            and self.construction_rule_ref is None
        ):
            raise MayeleContractError(
                "construction_rule_version requires construction_rule_ref"
            )


@dataclass(frozen=True, slots=True)
class KnowledgeSupportTrace:
    """Typed support lineage rooted in one observed statement."""

    support_ref: str
    statement: ObservedStatement
    scope: Optional[KnowledgeScope] = None
    interpretation_ref: Optional[str] = None
    candidate_ref: Optional[str] = None
    identity_resolution_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "support_ref", _required_text("support_ref", self.support_ref)
        )
        if not isinstance(self.statement, ObservedStatement):
            raise MayeleContractError("statement must be ObservedStatement")

        scope = self.statement.scope if self.scope is None else self.scope
        if not isinstance(scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")
        if _scope_rank(scope) < _scope_rank(self.statement.scope):
            raise MayeleContractError("support trace scope cannot widen statement scope")
        if (
            self.statement.scope.context_ref is not None
            and scope.context_ref != self.statement.scope.context_ref
        ):
            raise MayeleContractError(
                "support trace must preserve non-public statement context"
            )
        object.__setattr__(self, "scope", scope)

        object.__setattr__(
            self,
            "interpretation_ref",
            _optional_text("interpretation_ref", self.interpretation_ref),
        )
        object.__setattr__(
            self, "candidate_ref", _optional_text("candidate_ref", self.candidate_ref)
        )
        refs = tuple(_required_text("identity_resolution_ref", item) for item in self.identity_resolution_refs)
        if len(set(refs)) != len(refs):
            raise MayeleContractError("identity resolution refs must be unique")
        object.__setattr__(self, "identity_resolution_refs", refs)

    @property
    def passage(self):
        return self.statement.passage

    @property
    def artifact(self):
        return self.statement.passage.artifact

    @property
    def observation(self):
        return self.statement.passage.artifact.observation

    @property
    def source(self):
        return self.statement.passage.artifact.observation.source


def build_proposition_construction(
    candidate: WorldCandidate,
    constructed_at: datetime,
    *,
    identity_resolutions: Tuple[IdentityResolution, ...] = (),
    validity: Optional[TemporalValidity] = None,
    construction_rule_ref: Optional[str] = None,
    construction_rule_version: Optional[str] = None,
) -> PropositionConstruction:
    """Deterministically compose MY3/MY4 into an existing MY1 Proposition."""

    if not isinstance(
        candidate,
        (RealityCandidate, PropertyCandidate, RelationCandidate, ConditionCandidate),
    ):
        raise MayeleContractError("unsupported world candidate type")
    if candidate.status is CandidateStatus.REJECTED:
        raise MayeleContractError("REJECTED candidate cannot produce a Proposition")
    _aware_datetime("constructed_at", constructed_at)
    if validity is not None and not isinstance(validity, TemporalValidity):
        raise MayeleContractError("validity must be TemporalValidity or None")

    resolutions = tuple(identity_resolutions)
    if not all(isinstance(item, IdentityResolution) for item in resolutions):
        raise MayeleContractError(
            "identity_resolutions must contain IdentityResolution values"
        )
    used: list[IdentityResolution] = []

    if isinstance(candidate, RealityCandidate):
        referent = InterpretationReferent(
            ReferentKind.REALITY_CANDIDATE, candidate.candidate_ref
        )
        resolution = _resolution_for(referent, resolutions)
        used.append(resolution)
        source_referents = (referent,)
        target = resolution.reality
        kind = PropositionKind.REALITY_EXISTS
    elif isinstance(candidate, PropertyCandidate):
        source_referents = (candidate.subject,)
        reality_ref = _reality_ref_for(candidate.subject, resolutions, used)
        target = Property(reality_ref, candidate.attribute, candidate.value)
        kind = PropositionKind.PROPERTY_HOLDS
    elif isinstance(candidate, RelationCandidate):
        source_referents = tuple(item.referent for item in candidate.participants)
        participants = tuple(
            RelationParticipant(
                item.role,
                _reality_ref_for(item.referent, resolutions, used),
            )
            for item in candidate.participants
        )
        target = Relation(candidate.predicate, participants)
        kind = PropositionKind.RELATION_HOLDS
    else:
        source_referents = tuple(candidate.referents)
        for referent in candidate.referents:
            _reality_ref_for(referent, resolutions, used)
        target = Condition(candidate.expression)
        kind = PropositionKind.CONDITION_APPLIES

    unused = {
        item.resolution_ref for item in resolutions
    } - {item.resolution_ref for item in used}
    if unused:
        raise MayeleContractError(
            "identity_resolutions contains entries not used by this construction"
        )

    scope = _combine_scopes(
        candidate.scope,
        *(item.scope for item in used),
    )
    proposition = Proposition(kind, target, scope=scope, validity=validity)
    return PropositionConstruction(
        candidate_ref=candidate.candidate_ref,
        candidate_fingerprint=candidate.fingerprint,
        proposition=proposition,
        constructed_at=constructed_at,
        source_referents=source_referents,
        identity_resolutions=tuple(used),
        scope=scope,
        construction_rule_ref=construction_rule_ref,
        construction_rule_version=construction_rule_version,
    )


def build_knowledge_support(
    construction: PropositionConstruction,
    candidate: WorldCandidate,
    support_ref: str,
    disposition: SupportDisposition,
    *,
    statement: Optional[ObservedStatement] = None,
    metadata: Mapping[str, Any] | Tuple[Tuple[str, Any], ...] = (),
) -> tuple[KnowledgeSupport, KnowledgeSupportTrace]:
    """Create explicit support plus typed observation lineage; never an assessment."""

    if not isinstance(construction, PropositionConstruction):
        raise MayeleContractError("construction must be PropositionConstruction")
    if not isinstance(
        candidate,
        (RealityCandidate, PropertyCandidate, RelationCandidate, ConditionCandidate),
    ):
        raise MayeleContractError("candidate must be a world candidate")
    if candidate.candidate_ref != construction.candidate_ref:
        raise MayeleContractError("support candidate does not match construction")
    if candidate.fingerprint != construction.candidate_fingerprint:
        raise MayeleContractError("support candidate fingerprint mismatch")

    observed_statement = candidate.interpretation.statement if statement is None else statement
    if not isinstance(observed_statement, ObservedStatement):
        raise MayeleContractError("statement must be ObservedStatement")
    if (
        observed_statement.statement_ref
        != candidate.interpretation.statement.statement_ref
    ):
        raise MayeleContractError(
            "support statement must be the statement interpreted by the candidate"
        )

    support = KnowledgeSupport(
        construction.proposition.fingerprint,
        support_ref,
        disposition,
        metadata,
    )
    trace = KnowledgeSupportTrace(
        support_ref,
        observed_statement,
        interpretation_ref=candidate.interpretation.interpretation_ref,
        candidate_ref=candidate.candidate_ref,
        identity_resolution_refs=tuple(
            item.resolution_ref for item in construction.identity_resolutions
        ),
    )
    return support, trace
