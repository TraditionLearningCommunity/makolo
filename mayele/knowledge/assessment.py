from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

from mayele.common.contracts import KnowledgeScope, ScopeVisibility
from mayele.common.errors import MayeleContractError

from .construction import KnowledgeSupportTrace
from .contracts import (
    AssessmentStatus,
    KnowledgeSupport,
    Proposition,
    PropositionAssessment,
    SupportDisposition,
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
            raise MayeleContractError("all assessment scopes must be KnowledgeScope")

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
        raise MayeleContractError("assessment scope cannot widen its inputs")
    if inherited.context_ref is not None and requested.context_ref != inherited.context_ref:
        raise MayeleContractError(
            "assessment scope must preserve the inherited non-public context"
        )
    return requested


class PropositionComparisonStatus(str, Enum):
    COMPARABLE = "COMPARABLE"
    DISTINCT_CONTEXT = "DISTINCT_CONTEXT"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class PropositionComparison:
    """Explicit applicability comparison; it does not itself assert contradiction."""

    comparison_ref: str
    left_proposition_fingerprint: str
    right_proposition_fingerprint: str
    status: PropositionComparisonStatus
    compared_at: datetime
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "comparison_ref", _required_text("comparison_ref", self.comparison_ref)
        )
        object.__setattr__(
            self,
            "left_proposition_fingerprint",
            _required_text(
                "left_proposition_fingerprint", self.left_proposition_fingerprint
            ),
        )
        object.__setattr__(
            self,
            "right_proposition_fingerprint",
            _required_text(
                "right_proposition_fingerprint", self.right_proposition_fingerprint
            ),
        )
        if self.left_proposition_fingerprint == self.right_proposition_fingerprint:
            raise MayeleContractError("a Proposition comparison requires two distinct Propositions")
        try:
            status = PropositionComparisonStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid Proposition comparison status") from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self, "compared_at", _aware_datetime("compared_at", self.compared_at)
        )
        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("comparison scope must be KnowledgeScope")

    def involves(self, proposition_fingerprint: str) -> bool:
        return proposition_fingerprint in (
            self.left_proposition_fingerprint,
            self.right_proposition_fingerprint,
        )


@dataclass(frozen=True, slots=True)
class PropositionAssessmentTrace:
    """Lineage explaining one immutable PropositionAssessment decision."""

    assessment_ref: str
    assessment: PropositionAssessment
    support_refs: Tuple[str, ...] = ()
    comparison_refs: Tuple[str, ...] = ()
    assessment_rule_ref: Optional[str] = None
    assessment_rule_version: Optional[str] = None
    supersedes_assessment_ref: Optional[str] = None
    successor_proposition_fingerprint: Optional[str] = None
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "assessment_ref", _required_text("assessment_ref", self.assessment_ref)
        )
        if not isinstance(self.assessment, PropositionAssessment):
            raise MayeleContractError("assessment must be PropositionAssessment")

        support_refs = tuple(
            _required_text("support_ref", item) for item in self.support_refs
        )
        if len(set(support_refs)) != len(support_refs):
            raise MayeleContractError("assessment support_refs must be unique")
        object.__setattr__(self, "support_refs", support_refs)

        comparison_refs = tuple(
            _required_text("comparison_ref", item) for item in self.comparison_refs
        )
        if len(set(comparison_refs)) != len(comparison_refs):
            raise MayeleContractError("assessment comparison_refs must be unique")
        object.__setattr__(self, "comparison_refs", comparison_refs)

        object.__setattr__(
            self,
            "assessment_rule_ref",
            _optional_text("assessment_rule_ref", self.assessment_rule_ref),
        )
        object.__setattr__(
            self,
            "assessment_rule_version",
            _optional_text("assessment_rule_version", self.assessment_rule_version),
        )
        if self.assessment_rule_version is not None and self.assessment_rule_ref is None:
            raise MayeleContractError(
                "assessment_rule_version requires assessment_rule_ref"
            )

        object.__setattr__(
            self,
            "supersedes_assessment_ref",
            _optional_text(
                "supersedes_assessment_ref", self.supersedes_assessment_ref
            ),
        )
        if self.supersedes_assessment_ref == self.assessment_ref:
            raise MayeleContractError("an assessment cannot supersede itself")

        object.__setattr__(
            self,
            "successor_proposition_fingerprint",
            _optional_text(
                "successor_proposition_fingerprint",
                self.successor_proposition_fingerprint,
            ),
        )
        if (
            self.successor_proposition_fingerprint
            == self.assessment.proposition_fingerprint
        ):
            raise MayeleContractError(
                "a superseding Proposition must be distinct from the assessed Proposition"
            )
        if self.assessment.status is AssessmentStatus.SUPERSEDED:
            if self.successor_proposition_fingerprint is None:
                raise MayeleContractError(
                    "SUPERSEDED requires successor_proposition_fingerprint"
                )
        elif self.successor_proposition_fingerprint is not None:
            raise MayeleContractError(
                "successor_proposition_fingerprint is only valid for SUPERSEDED"
            )

        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("assessment trace scope must be KnowledgeScope")


def build_proposition_assessment(
    proposition: Proposition,
    status: AssessmentStatus,
    assessed_at: datetime,
    *,
    assessment_ref: str,
    supports: Tuple[KnowledgeSupport, ...] = (),
    support_traces: Tuple[KnowledgeSupportTrace, ...] = (),
    comparisons: Tuple[PropositionComparison, ...] = (),
    assessment_rule_ref: Optional[str] = None,
    assessment_rule_version: Optional[str] = None,
    supersedes_assessment_ref: Optional[str] = None,
    successor_proposition_fingerprint: Optional[str] = None,
    scope: Optional[KnowledgeScope] = None,
    metadata: Mapping[str, Any] | Tuple[Tuple[str, Any], ...] = (),
) -> tuple[PropositionAssessment, PropositionAssessmentTrace]:
    """Compose and validate an explicit epistemic decision; never choose its status."""

    if not isinstance(proposition, Proposition):
        raise MayeleContractError("proposition must be Proposition")
    _required_text("assessment_ref", assessment_ref)
    _aware_datetime("assessed_at", assessed_at)

    support_values = tuple(supports)
    if not all(isinstance(item, KnowledgeSupport) for item in support_values):
        raise MayeleContractError("supports must contain KnowledgeSupport values")
    support_refs = tuple(item.support_ref for item in support_values)
    if len(set(support_refs)) != len(support_refs):
        raise MayeleContractError("assessment supports must be unique")
    if any(
        item.proposition_fingerprint != proposition.fingerprint
        for item in support_values
    ):
        raise MayeleContractError("assessment support targets a different Proposition")

    trace_values = tuple(support_traces)
    if not all(isinstance(item, KnowledgeSupportTrace) for item in trace_values):
        raise MayeleContractError(
            "support_traces must contain KnowledgeSupportTrace values"
        )
    trace_refs = tuple(item.support_ref for item in trace_values)
    if len(set(trace_refs)) != len(trace_refs):
        raise MayeleContractError("assessment support traces must be unique")
    if set(trace_refs) != set(support_refs):
        raise MayeleContractError(
            "every support used by an assessment requires exactly one support trace"
        )

    comparison_values = tuple(comparisons)
    if not all(isinstance(item, PropositionComparison) for item in comparison_values):
        raise MayeleContractError(
            "comparisons must contain PropositionComparison values"
        )
    comparison_refs = tuple(item.comparison_ref for item in comparison_values)
    if len(set(comparison_refs)) != len(comparison_refs):
        raise MayeleContractError("assessment comparisons must be unique")
    if any(not item.involves(proposition.fingerprint) for item in comparison_values):
        raise MayeleContractError(
            "assessment comparison must involve the assessed Proposition"
        )

    inherited_scope = _combine_scopes(
        proposition.scope,
        *(item.scope for item in trace_values),
        *(item.scope for item in comparison_values),
    )
    assessment_scope = _derived_scope(inherited_scope, scope)

    assessment = PropositionAssessment(
        proposition.fingerprint,
        status,
        assessed_at,
        metadata,
    )
    trace = PropositionAssessmentTrace(
        assessment_ref=assessment_ref,
        assessment=assessment,
        support_refs=support_refs,
        comparison_refs=comparison_refs,
        assessment_rule_ref=assessment_rule_ref,
        assessment_rule_version=assessment_rule_version,
        supersedes_assessment_ref=supersedes_assessment_ref,
        successor_proposition_fingerprint=successor_proposition_fingerprint,
        scope=assessment_scope,
    )

    if assessment.status in (
        AssessmentStatus.ESTABLISHED,
        AssessmentStatus.PARTIALLY_SUPPORTED,
    ) and not support_values:
        raise MayeleContractError(
            f"{assessment.status.value} requires at least one explicit KnowledgeSupport"
        )

    if assessment.status is AssessmentStatus.CONTRADICTORY:
        has_contradicting_support = any(
            item.disposition is SupportDisposition.CONTRADICTS
            for item in support_values
        )
        has_comparable_proposition = any(
            item.status is PropositionComparisonStatus.COMPARABLE
            for item in comparison_values
        )
        if not (has_contradicting_support or has_comparable_proposition):
            raise MayeleContractError(
                "CONTRADICTORY requires explicit contradicting support or a comparable Proposition"
            )

    return assessment, trace
