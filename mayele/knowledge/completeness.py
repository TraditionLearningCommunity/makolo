from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from mayele.common.contracts import KnowledgeScope, ScopeVisibility
from mayele.common.errors import KnowledgeGateError, MayeleContractError

from .assessment import PropositionAssessmentTrace
from .contracts import Proposition, Reality


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


def _unique_refs(name: str, values: Tuple[str, ...]) -> Tuple[str, ...]:
    normalized = tuple(_required_text(name, value) for value in values)
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
        raise MayeleContractError("all completeness scopes must be KnowledgeScope")
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
        raise MayeleContractError("knowledge completeness scope cannot widen its inputs")
    if inherited.context_ref is not None and requested.context_ref != inherited.context_ref:
        raise MayeleContractError(
            "knowledge completeness scope must preserve the inherited context_ref"
        )
    return requested


class KnowledgeFacetStatus(str, Enum):
    KNOWN = "KNOWN"
    PARTIALLY_KNOWN = "PARTIALLY_KNOWN"
    UNKNOWN = "UNKNOWN"
    CONTRADICTORY = "CONTRADICTORY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class KnowledgeFacetState:
    """Derived completeness decision for one contextual knowledge facet."""

    facet_ref: str
    status: KnowledgeFacetStatus
    evaluated_at: datetime
    proposition_fingerprints: Tuple[str, ...] = ()
    assessment_refs: Tuple[str, ...] = ()
    applicability_basis_refs: Tuple[str, ...] = ()
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)

    def __post_init__(self) -> None:
        object.__setattr__(self, "facet_ref", _required_text("facet_ref", self.facet_ref))
        try:
            status = KnowledgeFacetStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid knowledge facet status") from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self, "evaluated_at", _aware_datetime("evaluated_at", self.evaluated_at)
        )
        object.__setattr__(
            self,
            "proposition_fingerprints",
            _unique_refs("proposition_fingerprint", tuple(self.proposition_fingerprints)),
        )
        object.__setattr__(
            self,
            "assessment_refs",
            _unique_refs("assessment_ref", tuple(self.assessment_refs)),
        )
        object.__setattr__(
            self,
            "applicability_basis_refs",
            _unique_refs(
                "applicability_basis_ref", tuple(self.applicability_basis_refs)
            ),
        )
        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")
        if (
            status is KnowledgeFacetStatus.NOT_APPLICABLE
            and not self.applicability_basis_refs
        ):
            raise MayeleContractError(
                "NOT_APPLICABLE requires an explicit applicability basis"
            )
        if status in (
            KnowledgeFacetStatus.KNOWN,
            KnowledgeFacetStatus.PARTIALLY_KNOWN,
            KnowledgeFacetStatus.CONTRADICTORY,
        ) and not self.assessment_refs:
            raise MayeleContractError(
                f"{status.value} completeness requires explicit assessment lineage"
            )


@dataclass(frozen=True, slots=True)
class KnowledgeCompleteness:
    """Facet-wise completeness projection for one Reality; never a percentage."""

    reality_ref: str
    evaluated_at: datetime
    facets: Tuple[KnowledgeFacetState, ...] = ()
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)
    rule_ref: Optional[str] = None
    rule_version: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "reality_ref", _required_text("reality_ref", self.reality_ref)
        )
        object.__setattr__(
            self, "evaluated_at", _aware_datetime("evaluated_at", self.evaluated_at)
        )
        facets = tuple(self.facets)
        if not all(isinstance(item, KnowledgeFacetState) for item in facets):
            raise MayeleContractError("facets must contain KnowledgeFacetState values")
        refs = [item.facet_ref for item in facets]
        if len(set(refs)) != len(refs):
            raise MayeleContractError("facet_ref values must be unique")
        if any(item.evaluated_at > self.evaluated_at for item in facets):
            raise MayeleContractError(
                "a completeness projection cannot use a future facet evaluation"
            )
        object.__setattr__(self, "facets", facets)
        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")
        object.__setattr__(self, "rule_ref", _optional_text("rule_ref", self.rule_ref))
        object.__setattr__(
            self, "rule_version", _optional_text("rule_version", self.rule_version)
        )
        if self.rule_version is not None and self.rule_ref is None:
            raise MayeleContractError("rule_version requires rule_ref")

    def facet(self, facet_ref: str) -> Optional[KnowledgeFacetState]:
        normalized = _required_text("facet_ref", facet_ref)
        return next((item for item in self.facets if item.facet_ref == normalized), None)


def build_knowledge_completeness(
    reality: Reality,
    evaluated_at: datetime,
    *,
    facets: Tuple[KnowledgeFacetState, ...] = (),
    scope: Optional[KnowledgeScope] = None,
    rule_ref: Optional[str] = None,
    rule_version: Optional[str] = None,
) -> KnowledgeCompleteness:
    """Compose explicit facet decisions without deriving statuses or scores."""

    if not isinstance(reality, Reality):
        raise MayeleContractError("reality must be Reality")
    _aware_datetime("evaluated_at", evaluated_at)
    facet_values = tuple(facets)
    inherited_scope = _combine_scopes(*(item.scope for item in facet_values))
    completeness_scope = _derived_scope(inherited_scope, scope)
    return KnowledgeCompleteness(
        reality_ref=reality.reality_ref,
        evaluated_at=evaluated_at,
        facets=facet_values,
        scope=completeness_scope,
        rule_ref=rule_ref,
        rule_version=rule_version,
    )


def validate_knowledge_completeness(
    reality: Reality,
    completeness: KnowledgeCompleteness,
    *,
    propositions: Tuple[Proposition, ...] = (),
    assessment_traces: Tuple[PropositionAssessmentTrace, ...] = (),
) -> KnowledgeCompleteness:
    """Pure MY7-A gate validating lineage, temporal bounds and scope."""

    if not isinstance(reality, Reality):
        raise KnowledgeGateError("reality must be Reality")
    if not isinstance(completeness, KnowledgeCompleteness):
        raise KnowledgeGateError("completeness must be KnowledgeCompleteness")
    if completeness.reality_ref != reality.reality_ref:
        raise KnowledgeGateError("completeness targets a different Reality")

    proposition_values = tuple(propositions)
    if not all(isinstance(item, Proposition) for item in proposition_values):
        raise KnowledgeGateError("propositions must contain Proposition values")
    proposition_by_fingerprint = {item.fingerprint: item for item in proposition_values}
    if len(proposition_by_fingerprint) != len(proposition_values):
        raise KnowledgeGateError("proposition fingerprints must be unique")

    trace_values = tuple(assessment_traces)
    if not all(isinstance(item, PropositionAssessmentTrace) for item in trace_values):
        raise KnowledgeGateError(
            "assessment_traces must contain PropositionAssessmentTrace values"
        )
    trace_by_ref = {item.assessment_ref: item for item in trace_values}
    if len(trace_by_ref) != len(trace_values):
        raise KnowledgeGateError("assessment_ref values must be unique")

    for facet in completeness.facets:
        selected_scopes: list[KnowledgeScope] = []
        for fingerprint in facet.proposition_fingerprints:
            proposition = proposition_by_fingerprint.get(fingerprint)
            if proposition is None:
                raise KnowledgeGateError(
                    "completeness references a Proposition missing from the inputs"
                )
            selected_scopes.append(proposition.scope)

        for assessment_ref in facet.assessment_refs:
            trace = trace_by_ref.get(assessment_ref)
            if trace is None:
                raise KnowledgeGateError(
                    "completeness references an Assessment missing from the inputs"
                )
            if trace.assessment.assessed_at > facet.evaluated_at:
                raise KnowledgeGateError(
                    "completeness cannot use an Assessment from the future"
                )
            if (
                trace.assessment.proposition_fingerprint
                not in facet.proposition_fingerprints
            ):
                raise KnowledgeGateError(
                    "assessment lineage must identify its Proposition fingerprint"
                )
            selected_scopes.append(trace.scope)

        if selected_scopes:
            try:
                inherited = _combine_scopes(*selected_scopes)
                _derived_scope(inherited, facet.scope)
            except MayeleContractError as exc:
                raise KnowledgeGateError(str(exc)) from exc

    try:
        expected = build_knowledge_completeness(
            reality,
            completeness.evaluated_at,
            facets=completeness.facets,
            scope=completeness.scope,
            rule_ref=completeness.rule_ref,
            rule_version=completeness.rule_version,
        )
    except MayeleContractError as exc:
        raise KnowledgeGateError(str(exc)) from exc
    if expected != completeness:
        raise KnowledgeGateError("completeness is inconsistent with its inputs")
    return completeness
