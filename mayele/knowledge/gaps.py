from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from mayele.common.contracts import KnowledgeScope, ScopeVisibility
from mayele.common.errors import KnowledgeGateError, MayeleContractError
from mayele.identity import IdentityResolution, IdentityResolutionStatus

from .assessment import PropositionAssessmentTrace
from .completeness import KnowledgeFacetStatus
from .contracts import AssessmentStatus
from .state import KnowledgeState


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
        raise MayeleContractError("all gap/revalidation scopes must be KnowledgeScope")
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
    parent: KnowledgeScope, child: Optional[KnowledgeScope]
) -> KnowledgeScope:
    if not isinstance(parent, KnowledgeScope):
        raise MayeleContractError("parent scope must be KnowledgeScope")
    if child is None:
        return parent
    if not isinstance(child, KnowledgeScope):
        raise MayeleContractError("scope must be KnowledgeScope")
    if _scope_rank(child) < _scope_rank(parent):
        raise MayeleContractError("gap/revalidation scope cannot widen KnowledgeState")
    if parent.context_ref is not None and child.context_ref != parent.context_ref:
        raise MayeleContractError("gap/revalidation scope must preserve context_ref")
    return child


class ResearchGapTargetKind(str, Enum):
    REALITY = "REALITY"
    FACET = "FACET"
    PROPOSITION = "PROPOSITION"
    IDENTITY = "IDENTITY"
    RELATION = "RELATION"


class ResearchGapReason(str, Enum):
    UNKNOWN = "UNKNOWN"
    PARTIALLY_KNOWN = "PARTIALLY_KNOWN"
    CONTRADICTORY = "CONTRADICTORY"
    UNRESOLVED_ASSESSMENT = "UNRESOLVED_ASSESSMENT"
    UNRESOLVED_IDENTITY = "UNRESOLVED_IDENTITY"
    PROVISIONAL_IDENTITY = "PROVISIONAL_IDENTITY"
    REVALIDATION_DUE = "REVALIDATION_DUE"
    STALE = "STALE"
    MISSING_RELATION = "MISSING_RELATION"


class RevalidationReason(str, Enum):
    REVALIDATION_DUE = "REVALIDATION_DUE"
    STALE_FOR_USE = "STALE_FOR_USE"
    EXPLICIT_REQUEST = "EXPLICIT_REQUEST"


class ResearchGapResolutionKind(str, Enum):
    RESOLVED = "RESOLVED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class ResearchGapTarget:
    kind: ResearchGapTargetKind
    ref: str

    def __post_init__(self) -> None:
        try:
            kind = ResearchGapTargetKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid ResearchGap target kind") from exc
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "ref", _required_text("target ref", self.ref))


@dataclass(frozen=True, slots=True)
class RevalidationNeed:
    """Explicit freshness need; it schedules nothing and negates nothing."""

    need_ref: str
    target_ref: str
    reason: RevalidationReason
    detected_at: datetime
    knowledge_state_ref: str
    basis_ref: str
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)
    due_at: Optional[datetime] = None
    revalidation_rule_ref: Optional[str] = None
    revalidation_rule_version: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "need_ref", _required_text("need_ref", self.need_ref))
        object.__setattr__(
            self, "target_ref", _required_text("target_ref", self.target_ref)
        )
        try:
            reason = RevalidationReason(self.reason)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid revalidation reason") from exc
        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self, "detected_at", _aware_datetime("detected_at", self.detected_at)
        )
        object.__setattr__(
            self,
            "knowledge_state_ref",
            _required_text("knowledge_state_ref", self.knowledge_state_ref),
        )
        object.__setattr__(
            self, "basis_ref", _required_text("basis_ref", self.basis_ref)
        )
        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")
        if self.due_at is not None:
            object.__setattr__(
                self, "due_at", _aware_datetime("due_at", self.due_at)
            )
        object.__setattr__(
            self,
            "revalidation_rule_ref",
            _optional_text("revalidation_rule_ref", self.revalidation_rule_ref),
        )
        object.__setattr__(
            self,
            "revalidation_rule_version",
            _optional_text(
                "revalidation_rule_version", self.revalidation_rule_version
            ),
        )
        if (
            self.revalidation_rule_version is not None
            and self.revalidation_rule_ref is None
        ):
            raise MayeleContractError(
                "revalidation_rule_version requires revalidation_rule_ref"
            )


@dataclass(frozen=True, slots=True)
class ResearchGap:
    """Actionable epistemic lack, distinct from a future ResearchMission."""

    gap_ref: str
    target: ResearchGapTarget
    reason: ResearchGapReason
    detected_at: datetime
    knowledge_state_ref: str
    basis_refs: Tuple[str, ...]
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)
    trigger_ref: Optional[str] = None
    revalidation_due_at: Optional[datetime] = None
    supersedes_gap_ref: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "gap_ref", _required_text("gap_ref", self.gap_ref))
        if not isinstance(self.target, ResearchGapTarget):
            raise MayeleContractError("target must be ResearchGapTarget")
        try:
            reason = ResearchGapReason(self.reason)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid ResearchGap reason") from exc
        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self, "detected_at", _aware_datetime("detected_at", self.detected_at)
        )
        object.__setattr__(
            self,
            "knowledge_state_ref",
            _required_text("knowledge_state_ref", self.knowledge_state_ref),
        )
        basis_refs = _unique_refs("basis_ref", tuple(self.basis_refs))
        if not basis_refs:
            raise MayeleContractError("ResearchGap requires explicit basis_refs")
        object.__setattr__(self, "basis_refs", basis_refs)
        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")
        object.__setattr__(
            self, "trigger_ref", _optional_text("trigger_ref", self.trigger_ref)
        )
        if self.revalidation_due_at is not None:
            object.__setattr__(
                self,
                "revalidation_due_at",
                _aware_datetime("revalidation_due_at", self.revalidation_due_at),
            )
        object.__setattr__(
            self,
            "supersedes_gap_ref",
            _optional_text("supersedes_gap_ref", self.supersedes_gap_ref),
        )
        if self.supersedes_gap_ref == self.gap_ref:
            raise MayeleContractError("a ResearchGap cannot supersede itself")


@dataclass(frozen=True, slots=True)
class ResearchGapResolution:
    gap_ref: str
    resolved_at: datetime
    resulting_state_ref: str
    resolution_kind: ResearchGapResolutionKind
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)

    def __post_init__(self) -> None:
        object.__setattr__(self, "gap_ref", _required_text("gap_ref", self.gap_ref))
        object.__setattr__(
            self, "resolved_at", _aware_datetime("resolved_at", self.resolved_at)
        )
        object.__setattr__(
            self,
            "resulting_state_ref",
            _required_text("resulting_state_ref", self.resulting_state_ref),
        )
        try:
            kind = ResearchGapResolutionKind(self.resolution_kind)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid ResearchGap resolution kind") from exc
        object.__setattr__(self, "resolution_kind", kind)
        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")


def _state_refs(state: KnowledgeState) -> set[str]:
    refs = {
        state.state_ref,
        state.reality_ref,
        *state.effective_assessment_refs,
        *state.effective_identity_resolution_refs,
    }
    for facet in state.completeness.facets:
        refs.add(facet.facet_ref)
        refs.update(facet.proposition_fingerprints)
        refs.update(facet.assessment_refs)
        refs.update(facet.applicability_basis_refs)
    return refs


def build_revalidation_need(
    state: KnowledgeState,
    target_ref: str,
    reason: RevalidationReason,
    detected_at: datetime,
    *,
    need_ref: str,
    basis_ref: str,
    due_at: Optional[datetime] = None,
    revalidation_rule_ref: Optional[str] = None,
    revalidation_rule_version: Optional[str] = None,
    scope: Optional[KnowledgeScope] = None,
) -> RevalidationNeed:
    if not isinstance(state, KnowledgeState):
        raise MayeleContractError("state must be KnowledgeState")
    target_ref = _required_text("target_ref", target_ref)
    basis_ref = _required_text("basis_ref", basis_ref)
    if target_ref not in _state_refs(state):
        raise MayeleContractError("revalidation target must exist in KnowledgeState")
    if basis_ref not in _state_refs(state):
        raise MayeleContractError("revalidation basis must exist in KnowledgeState")
    detected_at = _aware_datetime("detected_at", detected_at)
    if detected_at < state.as_of:
        raise MayeleContractError(
            "revalidation cannot be detected before its KnowledgeState"
        )
    need_scope = _derived_scope(state.scope, scope)
    return RevalidationNeed(
        need_ref=need_ref,
        target_ref=target_ref,
        reason=reason,
        detected_at=detected_at,
        knowledge_state_ref=state.state_ref,
        basis_ref=basis_ref,
        scope=need_scope,
        due_at=due_at,
        revalidation_rule_ref=revalidation_rule_ref,
        revalidation_rule_version=revalidation_rule_version,
    )


def validate_revalidation_need(
    state: KnowledgeState, need: RevalidationNeed
) -> RevalidationNeed:
    if not isinstance(state, KnowledgeState):
        raise KnowledgeGateError("state must be KnowledgeState")
    if not isinstance(need, RevalidationNeed):
        raise KnowledgeGateError("need must be RevalidationNeed")
    try:
        expected = build_revalidation_need(
            state,
            need.target_ref,
            need.reason,
            need.detected_at,
            need_ref=need.need_ref,
            basis_ref=need.basis_ref,
            due_at=need.due_at,
            revalidation_rule_ref=need.revalidation_rule_ref,
            revalidation_rule_version=need.revalidation_rule_version,
            scope=need.scope,
        )
    except MayeleContractError as exc:
        raise KnowledgeGateError(str(exc)) from exc
    if expected != need:
        raise KnowledgeGateError(
            "RevalidationNeed is inconsistent with KnowledgeState"
        )
    return need


def _validate_gap_reason(
    state: KnowledgeState,
    target: ResearchGapTarget,
    reason: ResearchGapReason,
    basis_refs: Tuple[str, ...],
    assessment_traces: Tuple[PropositionAssessmentTrace, ...],
    identity_resolutions: Tuple[IdentityResolution, ...],
    revalidation_needs: Tuple[RevalidationNeed, ...],
    trigger_ref: Optional[str],
) -> None:
    if (
        reason in (
            ResearchGapReason.UNKNOWN,
            ResearchGapReason.PARTIALLY_KNOWN,
            ResearchGapReason.PROVISIONAL_IDENTITY,
        )
        and trigger_ref is None
    ):
        raise MayeleContractError(
            "this ResearchGap reason requires an explicit trigger_ref"
        )

    if reason in (
        ResearchGapReason.UNKNOWN,
        ResearchGapReason.PARTIALLY_KNOWN,
        ResearchGapReason.CONTRADICTORY,
    ):
        if reason in (
            ResearchGapReason.UNKNOWN,
            ResearchGapReason.PARTIALLY_KNOWN,
        ) and trigger_ref is None:
            raise MayeleContractError(
                f"{reason.value} becomes a ResearchGap only for an explicit need"
            )
        if target.kind is not ResearchGapTargetKind.FACET:
            raise MayeleContractError(
                "completeness gap reasons require a FACET target"
            )
        facet = state.completeness.facet(target.ref)
        if facet is None:
            raise MayeleContractError(
                "ResearchGap FACET target is absent from completeness"
            )
        expected_status = {
            ResearchGapReason.UNKNOWN: KnowledgeFacetStatus.UNKNOWN,
            ResearchGapReason.PARTIALLY_KNOWN: KnowledgeFacetStatus.PARTIALLY_KNOWN,
            ResearchGapReason.CONTRADICTORY: KnowledgeFacetStatus.CONTRADICTORY,
        }[reason]
        if facet.status is not expected_status:
            raise MayeleContractError(
                "ResearchGap reason does not match facet completeness"
            )
        return

    if reason is ResearchGapReason.UNRESOLVED_ASSESSMENT:
        effective = set(state.effective_assessment_refs)
        traces = {item.assessment_ref: item for item in assessment_traces}
        if not any(
            ref in effective
            and ref in traces
            and traces[ref].assessment.status is AssessmentStatus.UNRESOLVED
            for ref in basis_refs
        ):
            raise MayeleContractError(
                "gap requires an effective UNRESOLVED Assessment"
            )
        return

    if reason in (
        ResearchGapReason.UNRESOLVED_IDENTITY,
        ResearchGapReason.PROVISIONAL_IDENTITY,
    ):
        if (
            reason is ResearchGapReason.PROVISIONAL_IDENTITY
            and trigger_ref is None
        ):
            raise MayeleContractError(
                "PROVISIONAL_IDENTITY becomes a ResearchGap only for an explicit need"
            )
        effective = set(state.effective_identity_resolution_refs)
        resolutions = {item.resolution_ref: item for item in identity_resolutions}
        expected = (
            IdentityResolutionStatus.UNRESOLVED
            if reason is ResearchGapReason.UNRESOLVED_IDENTITY
            else IdentityResolutionStatus.PROVISIONAL
        )
        if not any(
            ref in effective
            and ref in resolutions
            and resolutions[ref].status is expected
            for ref in basis_refs
        ):
            raise MayeleContractError(
                f"gap requires an effective {expected.value} IdentityResolution"
            )
        return

    if reason in (
        ResearchGapReason.REVALIDATION_DUE,
        ResearchGapReason.STALE,
    ):
        needs = {item.need_ref: item for item in revalidation_needs}
        expected_reasons = (
            {RevalidationReason.REVALIDATION_DUE}
            if reason is ResearchGapReason.REVALIDATION_DUE
            else {RevalidationReason.STALE_FOR_USE}
        )
        if not any(
            ref in needs
            and needs[ref].knowledge_state_ref == state.state_ref
            and needs[ref].reason in expected_reasons
            for ref in basis_refs
        ):
            raise MayeleContractError("gap requires a matching RevalidationNeed")
        return

    if reason is ResearchGapReason.MISSING_RELATION:
        if target.kind is not ResearchGapTargetKind.RELATION:
            raise MayeleContractError("MISSING_RELATION requires a RELATION target")
        if trigger_ref is None:
            raise MayeleContractError(
                "MISSING_RELATION requires an explicit trigger_ref explaining the need"
            )


def build_research_gap(
    state: KnowledgeState,
    target: ResearchGapTarget,
    reason: ResearchGapReason,
    detected_at: datetime,
    *,
    gap_ref: str,
    basis_refs: Tuple[str, ...],
    assessment_traces: Optional[Tuple[PropositionAssessmentTrace, ...]] = None,
    identity_resolutions: Optional[Tuple[IdentityResolution, ...]] = None,
    revalidation_needs: Optional[Tuple[RevalidationNeed, ...]] = None,
    trigger_ref: Optional[str] = None,
    revalidation_due_at: Optional[datetime] = None,
    supersedes_gap_ref: Optional[str] = None,
    scope: Optional[KnowledgeScope] = None,
) -> ResearchGap:
    """Build one explicitly requested gap; UNKNOWN is never auto-expanded."""

    if not isinstance(state, KnowledgeState):
        raise MayeleContractError("state must be KnowledgeState")
    if not isinstance(target, ResearchGapTarget):
        raise MayeleContractError("target must be ResearchGapTarget")
    try:
        reason = ResearchGapReason(reason)
    except (TypeError, ValueError) as exc:
        raise MayeleContractError("invalid ResearchGap reason") from exc
    detected_at = _aware_datetime("detected_at", detected_at)
    if detected_at < state.as_of:
        raise MayeleContractError("ResearchGap cannot predate its KnowledgeState")
    normalized_basis = _unique_refs("basis_ref", tuple(basis_refs))
    if not normalized_basis:
        raise MayeleContractError("ResearchGap requires explicit basis_refs")
    if reason not in (
        ResearchGapReason.REVALIDATION_DUE,
        ResearchGapReason.STALE,
    ):
        allowed = _state_refs(state)
        if any(ref not in allowed for ref in normalized_basis):
            raise MayeleContractError(
                "ResearchGap basis must come from KnowledgeState"
            )
    _validate_gap_reason(
        state,
        target,
        reason,
        normalized_basis,
        tuple(assessment_traces),
        tuple(identity_resolutions),
        tuple(revalidation_needs),
        trigger_ref,
    )
    gap_scope = _derived_scope(state.scope, scope)
    return ResearchGap(
        gap_ref=gap_ref,
        target=target,
        reason=reason,
        detected_at=detected_at,
        knowledge_state_ref=state.state_ref,
        basis_refs=normalized_basis,
        scope=gap_scope,
        trigger_ref=trigger_ref,
        revalidation_due_at=revalidation_due_at,
        supersedes_gap_ref=supersedes_gap_ref,
    )


def validate_research_gap(
    state: KnowledgeState,
    gap: ResearchGap,
    *,
    assessment_traces: Tuple[PropositionAssessmentTrace, ...] = (),
    identity_resolutions: Tuple[IdentityResolution, ...] = (),
    revalidation_needs: Tuple[RevalidationNeed, ...] = (),
) -> ResearchGap:
    if not isinstance(gap, ResearchGap):
        raise KnowledgeGateError("gap must be ResearchGap")
    try:
        expected = build_research_gap(
            state,
            gap.target,
            gap.reason,
            gap.detected_at,
            gap_ref=gap.gap_ref,
            basis_refs=gap.basis_refs,
            assessment_traces=tuple(assessment_traces),
            identity_resolutions=tuple(identity_resolutions),
            revalidation_needs=tuple(revalidation_needs),
            trigger_ref=gap.trigger_ref,
            revalidation_due_at=gap.revalidation_due_at,
            supersedes_gap_ref=gap.supersedes_gap_ref,
            scope=gap.scope,
        )
    except MayeleContractError as exc:
        raise KnowledgeGateError(str(exc)) from exc
    if expected != gap:
        raise KnowledgeGateError(
            "ResearchGap is inconsistent with KnowledgeState"
        )
    return gap


def resolve_research_gap(
    gap: ResearchGap,
    resulting_state: KnowledgeState,
    resolved_at: datetime,
    *,
    resolution_kind: ResearchGapResolutionKind = ResearchGapResolutionKind.RESOLVED,
    assessment_traces: Tuple[PropositionAssessmentTrace, ...] = (),
    identity_resolutions: Tuple[IdentityResolution, ...] = (),
    revalidation_needs: Tuple[RevalidationNeed, ...] = (),
    scope: Optional[KnowledgeScope] = None,
) -> ResearchGapResolution:
    """Record resolution without mutating the historical ResearchGap."""

    if not isinstance(gap, ResearchGap):
        raise MayeleContractError("gap must be ResearchGap")
    if not isinstance(resulting_state, KnowledgeState):
        raise MayeleContractError("resulting_state must be KnowledgeState")
    resolved_at = _aware_datetime("resolved_at", resolved_at)
    if resolved_at < gap.detected_at or resolved_at < resulting_state.as_of:
        raise MayeleContractError(
            "gap resolution cannot predate its gap or resulting state"
        )
    if resulting_state.state_ref == gap.knowledge_state_ref:
        raise MayeleContractError("gap resolution requires a new KnowledgeState")
    try:
        kind = ResearchGapResolutionKind(resolution_kind)
    except (TypeError, ValueError) as exc:
        raise MayeleContractError("invalid ResearchGap resolution kind") from exc

    if kind is ResearchGapResolutionKind.RESOLVED:
        if (
            gap.reason is ResearchGapReason.UNRESOLVED_ASSESSMENT
            and assessment_traces is None
        ):
            raise MayeleContractError(
                "resolving an assessment gap requires explicit assessment lineage"
            )
        if (
            gap.reason in (
                ResearchGapReason.UNRESOLVED_IDENTITY,
                ResearchGapReason.PROVISIONAL_IDENTITY,
            )
            and identity_resolutions is None
        ):
            raise MayeleContractError(
                "resolving an identity gap requires explicit identity lineage"
            )
        if (
            gap.reason in (
                ResearchGapReason.REVALIDATION_DUE,
                ResearchGapReason.STALE,
            )
            and revalidation_needs is None
        ):
            raise MayeleContractError(
                "resolving a revalidation gap requires explicit revalidation lineage"
            )

        assessment_values = tuple(assessment_traces or ())
        identity_values = tuple(identity_resolutions or ())
        revalidation_values = tuple(revalidation_needs or ())
        effective_assessments = set(resulting_state.effective_assessment_refs)
        traces_by_ref = {
            item.assessment_ref: item for item in assessment_values
        }
        effective_resolutions = set(
            resulting_state.effective_identity_resolution_refs
        )
        resolutions_by_ref = {
            item.resolution_ref: item for item in identity_values
        }

        if gap.reason is ResearchGapReason.UNRESOLVED_ASSESSMENT:
            if any(
                ref in traces_by_ref
                and traces_by_ref[ref].assessment.status
                is AssessmentStatus.UNRESOLVED
                and traces_by_ref[ref].assessment.proposition_fingerprint
                == gap.target.ref
                for ref in effective_assessments
            ):
                raise MayeleContractError(
                    "resulting KnowledgeState still contains an unresolved Assessment"
                )

        if gap.reason in (
            ResearchGapReason.UNRESOLVED_IDENTITY,
            ResearchGapReason.PROVISIONAL_IDENTITY,
        ):
            basis_resolutions = [
                resolutions_by_ref[ref]
                for ref in gap.basis_refs
                if ref in resolutions_by_ref
            ]
            referents = {item.referent for item in basis_resolutions}
            expected_status = (
                IdentityResolutionStatus.UNRESOLVED
                if gap.reason is ResearchGapReason.UNRESOLVED_IDENTITY
                else IdentityResolutionStatus.PROVISIONAL
            )
            if any(
                ref in resolutions_by_ref
                and resolutions_by_ref[ref].referent in referents
                and resolutions_by_ref[ref].status is expected_status
                for ref in effective_resolutions
            ):
                raise MayeleContractError(
                    "resulting KnowledgeState still contains the same identity gap"
                )

        if gap.reason in (
            ResearchGapReason.REVALIDATION_DUE,
            ResearchGapReason.STALE,
        ):
            expected_reasons = (
                {RevalidationReason.REVALIDATION_DUE}
                if gap.reason is ResearchGapReason.REVALIDATION_DUE
                else {RevalidationReason.STALE_FOR_USE}
            )
            if any(
                item.knowledge_state_ref == resulting_state.state_ref
                and item.target_ref == gap.target.ref
                and item.reason in expected_reasons
                for item in revalidation_values
            ):
                raise MayeleContractError(
                    "resulting KnowledgeState still requires revalidation"
                )

    if (
        kind is ResearchGapResolutionKind.RESOLVED
        and gap.target.kind is ResearchGapTargetKind.FACET
    ):
        facet = resulting_state.completeness.facet(gap.target.ref)
        if facet is None:
            raise MayeleContractError(
                "resolved facet must exist in resulting KnowledgeState"
            )
        still_active = {
            ResearchGapReason.UNKNOWN: KnowledgeFacetStatus.UNKNOWN,
            ResearchGapReason.PARTIALLY_KNOWN: KnowledgeFacetStatus.PARTIALLY_KNOWN,
            ResearchGapReason.CONTRADICTORY: KnowledgeFacetStatus.CONTRADICTORY,
        }.get(gap.reason)
        if still_active is not None and facet.status is still_active:
            raise MayeleContractError(
                "resulting KnowledgeState still contains the same gap"
            )

    inherited_scope = _combine_scopes(gap.scope, resulting_state.scope)
    resolution_scope = _derived_scope(inherited_scope, scope)
    return ResearchGapResolution(
        gap_ref=gap.gap_ref,
        resolved_at=resolved_at,
        resulting_state_ref=resulting_state.state_ref,
        resolution_kind=kind,
        scope=resolution_scope,
    )
