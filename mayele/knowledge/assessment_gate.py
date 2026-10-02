from __future__ import annotations

from typing import Iterable

from mayele.common.contracts import ScopeVisibility
from mayele.common.errors import KnowledgeGateError

from .assessment import (
    PropositionAssessmentTrace,
    PropositionComparison,
    build_proposition_assessment,
)
from .contracts import KnowledgeSupport, Proposition, PropositionAssessment
from .construction import KnowledgeSupportTrace


SENSITIVE_METADATA_TOKENS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "private_key",
    "access_token",
    "refresh_token",
    "credential",
)

AUTHORITY_MUTATION_KEYS = {
    "grant_permission",
    "grant_mandate",
    "grant_access",
    "confirm_payment",
    "authorize_payment",
    "modify_capacity",
    "modify_activity",
    "modify_journey",
    "modify_requirement",
}


def _metadata_keys(value: PropositionAssessment) -> set[str]:
    return {key.casefold() for key, _metadata_value in value.metadata}


def validate_proposition_assessment(
    proposition: Proposition,
    assessment: PropositionAssessment,
    trace: PropositionAssessmentTrace,
    *,
    supports: tuple[KnowledgeSupport, ...] = (),
    support_traces: tuple[KnowledgeSupportTrace, ...] = (),
    comparisons: tuple[PropositionComparison, ...] = (),
) -> PropositionAssessment:
    """Pure MY6 gate: validate explicit lineage without choosing a status."""

    if not isinstance(proposition, Proposition):
        raise KnowledgeGateError("proposition must be Proposition")
    if not isinstance(assessment, PropositionAssessment):
        raise KnowledgeGateError("assessment must be PropositionAssessment")
    if not isinstance(trace, PropositionAssessmentTrace):
        raise KnowledgeGateError("trace must be PropositionAssessmentTrace")
    if trace.assessment != assessment:
        raise KnowledgeGateError("assessment trace must reference the assessed decision")
    if assessment.proposition_fingerprint != proposition.fingerprint:
        raise KnowledgeGateError("assessment targets a different Proposition")

    try:
        expected_assessment, expected_trace = build_proposition_assessment(
            proposition,
            assessment.status,
            assessment.assessed_at,
            assessment_ref=trace.assessment_ref,
            supports=tuple(supports),
            support_traces=tuple(support_traces),
            comparisons=tuple(comparisons),
            assessment_rule_ref=trace.assessment_rule_ref,
            assessment_rule_version=trace.assessment_rule_version,
            supersedes_assessment_ref=trace.supersedes_assessment_ref,
            successor_proposition_fingerprint=trace.successor_proposition_fingerprint,
            scope=trace.scope,
            metadata=assessment.metadata,
        )
    except Exception as exc:
        if isinstance(exc, KnowledgeGateError):
            raise
        raise KnowledgeGateError(str(exc)) from exc

    if expected_assessment != assessment:
        raise KnowledgeGateError("assessment is inconsistent with its Proposition lineage")
    if expected_trace != trace:
        raise KnowledgeGateError("assessment trace is inconsistent with its inputs")

    trace_by_ref = {item.support_ref: item for item in support_traces}
    for support_ref in trace.support_refs:
        support_trace = trace_by_ref.get(support_ref)
        if support_trace is None:
            raise KnowledgeGateError("assessment support trace is missing")
        if support_trace.passage is not support_trace.statement.passage:
            raise KnowledgeGateError("assessment support Passage lineage is invalid")
        if support_trace.artifact is not support_trace.passage.artifact:
            raise KnowledgeGateError("assessment support Artifact lineage is invalid")
        if support_trace.observation is not support_trace.artifact.observation:
            raise KnowledgeGateError("assessment support Observation lineage is invalid")
        if support_trace.source is not support_trace.observation.source:
            raise KnowledgeGateError("assessment support Source lineage is invalid")

    keys = _metadata_keys(assessment)
    if trace.scope.visibility is ScopeVisibility.PUBLIC:
        for key in keys:
            if any(token in key for token in SENSITIVE_METADATA_TOKENS):
                raise KnowledgeGateError(
                    "public assessment metadata must not contain secrets"
                )
    if keys.intersection(AUTHORITY_MUTATION_KEYS):
        raise KnowledgeGateError(
            "Mayele assessment metadata cannot mutate Makolo authority or domains"
        )

    return assessment


def validate_assessment_history(
    traces: Iterable[PropositionAssessmentTrace],
) -> tuple[PropositionAssessmentTrace, ...]:
    """Validate reassessment lineage without collapsing historical decisions."""

    values = tuple(traces)
    if not all(isinstance(item, PropositionAssessmentTrace) for item in values):
        raise KnowledgeGateError(
            "assessment history must contain PropositionAssessmentTrace values"
        )

    refs = [item.assessment_ref for item in values]
    if len(set(refs)) != len(refs):
        raise KnowledgeGateError("assessment_ref values must be unique in one history")
    by_ref = {item.assessment_ref: item for item in values}

    for item in values:
        superseded_ref = item.supersedes_assessment_ref
        if superseded_ref is None:
            continue
        previous = by_ref.get(superseded_ref)
        if previous is None:
            raise KnowledgeGateError(
                "supersedes_assessment_ref must identify an assessment in the history"
            )
        if (
            previous.assessment.proposition_fingerprint
            != item.assessment.proposition_fingerprint
        ):
            raise KnowledgeGateError(
                "an assessment can supersede only an assessment of the same Proposition"
            )
        if previous.assessment.assessed_at >= item.assessment.assessed_at:
            raise KnowledgeGateError(
                "a superseding assessment must be later than the assessment it supersedes"
            )

    return values
