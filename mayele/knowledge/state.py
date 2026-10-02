from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

from mayele.common.contracts import KnowledgeScope, ScopeVisibility
from mayele.common.errors import KnowledgeGateError, MayeleContractError
from mayele.identity import IdentityResolution

from .assessment import PropositionAssessmentTrace
from .assessment_gate import validate_assessment_history
from .completeness import KnowledgeCompleteness
from .contracts import Reality


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise MayeleContractError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise MayeleContractError(f"{name} must not be empty")
    return normalized


def _aware_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise MayeleContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise MayeleContractError(f"{name} must be timezone-aware")
    return value


def _unique_refs(name: str, values: Tuple[str, ...]) -> Tuple[str, ...]:
    normalized = tuple(_required_text(name, item) for item in values)
    if len(set(normalized)) != len(normalized):
        raise MayeleContractError(f"{name} values must be unique")
    return normalized


def _scope_rank(scope: KnowledgeScope) -> int:
    return {
        ScopeVisibility.PUBLIC: 0,
        ScopeVisibility.RESTRICTED: 1,
        ScopeVisibility.PRIVATE: 2,
    }[scope.visibility]


def _combine_scopes(*scopes: KnowledgeScope) -> KnowledgeScope:
    if not scopes:
        return KnowledgeScope()
    if not all(isinstance(scope, KnowledgeScope) for scope in scopes):
        raise MayeleContractError("all state scopes must be KnowledgeScope")
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


def _derived_scope(
    inherited: KnowledgeScope, requested: Optional[KnowledgeScope]
) -> KnowledgeScope:
    if requested is None:
        return inherited
    if not isinstance(requested, KnowledgeScope):
        raise MayeleContractError("scope must be KnowledgeScope")
    if _scope_rank(requested) < _scope_rank(inherited):
        raise MayeleContractError("KnowledgeState scope cannot widen its inputs")
    if inherited.context_ref is not None and requested.context_ref != inherited.context_ref:
        raise MayeleContractError("KnowledgeState must preserve the inherited context_ref")
    return requested


def _validate_resolution_history(
    resolutions: Tuple[IdentityResolution, ...],
) -> Tuple[IdentityResolution, ...]:
    values = tuple(resolutions)
    if not all(isinstance(item, IdentityResolution) for item in values):
        raise MayeleContractError(
            "identity_resolutions must contain IdentityResolution values"
        )
    refs = [item.resolution_ref for item in values]
    if len(set(refs)) != len(refs):
        raise MayeleContractError("resolution_ref values must be unique")
    by_ref = {item.resolution_ref: item for item in values}
    for item in values:
        previous_ref = item.supersedes_resolution_ref
        if previous_ref is None:
            continue
        previous = by_ref.get(previous_ref)
        if previous is None:
            raise MayeleContractError(
                "supersedes_resolution_ref must identify a resolution in the history"
            )
        if previous.referent != item.referent:
            raise MayeleContractError(
                "an IdentityResolution can supersede only the same referent"
            )
        if previous.resolved_at >= item.resolved_at:
            raise MayeleContractError(
                "a superseding IdentityResolution must be later than its predecessor"
            )
    return values


def _effective_assessment_refs(
    traces: Tuple[PropositionAssessmentTrace, ...], as_of: datetime
) -> Tuple[str, ...]:
    validate_assessment_history(traces)
    eligible = tuple(item for item in traces if item.assessment.assessed_at <= as_of)
    eligible_refs = {item.assessment_ref for item in eligible}
    superseded = {
        item.supersedes_assessment_ref
        for item in eligible
        if item.supersedes_assessment_ref in eligible_refs
    }
    return tuple(
        sorted(
            item.assessment_ref
            for item in eligible
            if item.assessment_ref not in superseded
        )
    )


def _effective_resolution_refs(
    resolutions: Tuple[IdentityResolution, ...], as_of: datetime
) -> Tuple[str, ...]:
    _validate_resolution_history(resolutions)
    eligible = tuple(item for item in resolutions if item.resolved_at <= as_of)
    eligible_refs = {item.resolution_ref for item in eligible}
    superseded = {
        item.supersedes_resolution_ref
        for item in eligible
        if item.supersedes_resolution_ref in eligible_refs
    }
    return tuple(
        sorted(
            item.resolution_ref
            for item in eligible
            if item.resolution_ref not in superseded
        )
    )


@dataclass(frozen=True, slots=True)
class KnowledgeState:
    """Bounded, reproducible epistemic projection at one explicit as_of instant."""

    state_ref: str
    reality_ref: str
    as_of: datetime
    effective_assessment_refs: Tuple[str, ...]
    effective_identity_resolution_refs: Tuple[str, ...]
    completeness: KnowledgeCompleteness
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_ref", _required_text("state_ref", self.state_ref))
        object.__setattr__(
            self, "reality_ref", _required_text("reality_ref", self.reality_ref)
        )
        object.__setattr__(self, "as_of", _aware_datetime("as_of", self.as_of))
        object.__setattr__(
            self,
            "effective_assessment_refs",
            _unique_refs(
                "effective_assessment_ref", tuple(self.effective_assessment_refs)
            ),
        )
        object.__setattr__(
            self,
            "effective_identity_resolution_refs",
            _unique_refs(
                "effective_identity_resolution_ref",
                tuple(self.effective_identity_resolution_refs),
            ),
        )
        if not isinstance(self.completeness, KnowledgeCompleteness):
            raise MayeleContractError("completeness must be KnowledgeCompleteness")
        if self.completeness.reality_ref != self.reality_ref:
            raise MayeleContractError("completeness must target the same Reality")
        if self.completeness.evaluated_at > self.as_of:
            raise MayeleContractError("KnowledgeState cannot use future completeness")
        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")


def build_knowledge_state(
    reality: Reality,
    as_of: datetime,
    *,
    state_ref: str,
    completeness: KnowledgeCompleteness,
    assessment_traces: Tuple[PropositionAssessmentTrace, ...] = (),
    identity_resolutions: Tuple[IdentityResolution, ...] = (),
    scope: Optional[KnowledgeScope] = None,
) -> KnowledgeState:
    """Project effective lineage at as_of; never uses latest-timestamp wins."""

    if not isinstance(reality, Reality):
        raise MayeleContractError("reality must be Reality")
    as_of = _aware_datetime("as_of", as_of)
    if not isinstance(completeness, KnowledgeCompleteness):
        raise MayeleContractError("completeness must be KnowledgeCompleteness")
    if completeness.reality_ref != reality.reality_ref:
        raise MayeleContractError("completeness targets a different Reality")
    if completeness.evaluated_at > as_of:
        raise MayeleContractError("KnowledgeState cannot use future completeness")

    traces = tuple(assessment_traces)
    resolutions = tuple(identity_resolutions)
    effective_assessments = _effective_assessment_refs(traces, as_of)
    effective_resolutions = _effective_resolution_refs(resolutions, as_of)
    trace_by_ref = {item.assessment_ref: item for item in traces}
    resolution_by_ref = {item.resolution_ref: item for item in resolutions}
    inherited_scope = _combine_scopes(
        completeness.scope,
        *(trace_by_ref[ref].scope for ref in effective_assessments),
        *(resolution_by_ref[ref].scope for ref in effective_resolutions),
    )
    state_scope = _derived_scope(inherited_scope, scope)
    return KnowledgeState(
        state_ref=state_ref,
        reality_ref=reality.reality_ref,
        as_of=as_of,
        effective_assessment_refs=effective_assessments,
        effective_identity_resolution_refs=effective_resolutions,
        completeness=completeness,
        scope=state_scope,
    )


def validate_knowledge_state(
    reality: Reality,
    state: KnowledgeState,
    *,
    assessment_traces: Tuple[PropositionAssessmentTrace, ...] = (),
    identity_resolutions: Tuple[IdentityResolution, ...] = (),
) -> KnowledgeState:
    """Pure MY7-B gate; the history is read, never collapsed or mutated."""

    if not isinstance(reality, Reality):
        raise KnowledgeGateError("reality must be Reality")
    if not isinstance(state, KnowledgeState):
        raise KnowledgeGateError("state must be KnowledgeState")
    if state.reality_ref != reality.reality_ref:
        raise KnowledgeGateError("KnowledgeState targets a different Reality")
    try:
        expected = build_knowledge_state(
            reality,
            state.as_of,
            state_ref=state.state_ref,
            completeness=state.completeness,
            assessment_traces=tuple(assessment_traces),
            identity_resolutions=tuple(identity_resolutions),
            scope=state.scope,
        )
    except Exception as exc:
        if isinstance(exc, KnowledgeGateError):
            raise
        raise KnowledgeGateError(str(exc)) from exc
    if expected != state:
        raise KnowledgeGateError(
            "KnowledgeState does not match effective lineage at as_of"
        )
    return state
