from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from mayele.cognition import (
    CandidateStatus,
    ConditionCandidate,
    PropertyCandidate,
    RealityCandidate,
    RelationCandidate,
    WorldCandidate,
)
from mayele.common.errors import KnowledgeGateError
from .contracts import (
    KnowledgeSupport,
    Proposition,
    PropositionKind,
)
from .construction import (
    KnowledgeSupportTrace,
    PropositionConstruction,
    build_proposition_construction,
)
from .semantics import KnowledgeValue


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
}


@dataclass(frozen=True, slots=True)
class KnowledgeCandidate:
    proposition: Proposition
    supports: tuple[KnowledgeSupport, ...] = ()
    expected_fingerprint: Optional[str] = None
    support_required: bool = False


def _metadata_keys(support: KnowledgeSupport) -> set[str]:
    return {key.casefold() for key, _value in support.metadata}


def validate_candidate(candidate: KnowledgeCandidate) -> Proposition:
    """Pure deterministic MY1 gate. It performs no persistence or I/O."""

    if not isinstance(candidate, KnowledgeCandidate):
        raise KnowledgeGateError("candidate must be a KnowledgeCandidate")
    proposition = candidate.proposition
    if not isinstance(proposition, Proposition):
        raise KnowledgeGateError("candidate proposition is invalid")

    fingerprint = proposition.fingerprint
    if (
        candidate.expected_fingerprint is not None
        and candidate.expected_fingerprint != fingerprint
    ):
        raise KnowledgeGateError("proposition fingerprint mismatch")

    supports = tuple(candidate.supports)
    if candidate.support_required and not supports:
        raise KnowledgeGateError("at least one support is required")

    for support in supports:
        if not isinstance(support, KnowledgeSupport):
            raise KnowledgeGateError("supports must be KnowledgeSupport values")
        if support.proposition_fingerprint != fingerprint:
            raise KnowledgeGateError("support targets a different proposition")

        keys = _metadata_keys(support)
        for key in keys:
            if any(token in key for token in SENSITIVE_METADATA_TOKENS):
                raise KnowledgeGateError(
                    "public knowledge metadata must not contain secrets"
                )
        if keys.intersection(AUTHORITY_MUTATION_KEYS):
            raise KnowledgeGateError(
                "Mayele knowledge cannot mutate Makolo authority or payment"
            )

    # UNKNOWN remains an explicit semantic value. The gate never coerces it
    # into False, None, CLOSED or NOT_APPLICABLE.
    if proposition.kind is PropositionKind.PROPERTY_HOLDS:
        value = proposition.target.value
        if value is KnowledgeValue.UNKNOWN:
            pass

    return proposition


def validate_many(
    candidates: Iterable[KnowledgeCandidate],
) -> tuple[Proposition, ...]:
    return tuple(validate_candidate(candidate) for candidate in candidates)


def validate_proposition_construction(
    construction: PropositionConstruction,
    candidate: WorldCandidate,
) -> Proposition:
    """Pure MY5 gate: validate derivation lineage without assessing truth."""

    if not isinstance(construction, PropositionConstruction):
        raise KnowledgeGateError("construction must be PropositionConstruction")
    if not isinstance(
        candidate,
        (RealityCandidate, PropertyCandidate, RelationCandidate, ConditionCandidate),
    ):
        raise KnowledgeGateError("candidate must be a world candidate")
    if candidate.status is CandidateStatus.REJECTED:
        raise KnowledgeGateError("REJECTED candidate cannot produce a Proposition")
    if construction.candidate_ref != candidate.candidate_ref:
        raise KnowledgeGateError("construction candidate_ref mismatch")
    if construction.candidate_fingerprint != candidate.fingerprint:
        raise KnowledgeGateError("construction candidate fingerprint mismatch")

    expected_kind = {
        RealityCandidate: PropositionKind.REALITY_EXISTS,
        PropertyCandidate: PropositionKind.PROPERTY_HOLDS,
        RelationCandidate: PropositionKind.RELATION_HOLDS,
        ConditionCandidate: PropositionKind.CONDITION_APPLIES,
    }[type(candidate)]
    if construction.proposition.kind is not expected_kind:
        raise KnowledgeGateError("candidate maps to the wrong PropositionKind")

    try:
        expected = build_proposition_construction(
            candidate,
            construction.constructed_at,
            identity_resolutions=construction.identity_resolutions,
            validity=construction.proposition.validity,
            construction_rule_ref=construction.construction_rule_ref,
            construction_rule_version=construction.construction_rule_version,
        )
    except Exception as exc:
        if isinstance(exc, KnowledgeGateError):
            raise
        raise KnowledgeGateError(str(exc)) from exc

    if expected.source_referents != construction.source_referents:
        raise KnowledgeGateError(
            "construction must preserve the candidate source referents"
        )
    if expected.proposition != construction.proposition:
        raise KnowledgeGateError(
            "constructed Proposition is inconsistent with candidate and identity lineage"
        )
    if expected.scope != construction.scope:
        raise KnowledgeGateError("construction scope is inconsistent with its inputs")

    validate_candidate(
        KnowledgeCandidate(
            construction.proposition,
            expected_fingerprint=construction.proposition.fingerprint,
        )
    )
    return construction.proposition


def validate_knowledge_support_lineage(
    support: KnowledgeSupport,
    trace: KnowledgeSupportTrace,
    construction: PropositionConstruction,
    candidate: WorldCandidate,
) -> KnowledgeSupport:
    """Validate support -> Statement -> Passage -> Artifact -> Observation -> Source."""

    validate_proposition_construction(construction, candidate)
    if not isinstance(support, KnowledgeSupport):
        raise KnowledgeGateError("support must be KnowledgeSupport")
    if not isinstance(trace, KnowledgeSupportTrace):
        raise KnowledgeGateError("trace must be KnowledgeSupportTrace")
    if support.support_ref != trace.support_ref:
        raise KnowledgeGateError("support_ref does not match its typed trace")
    if support.proposition_fingerprint != construction.proposition.fingerprint:
        raise KnowledgeGateError("support targets a different Proposition")
    if trace.candidate_ref != candidate.candidate_ref:
        raise KnowledgeGateError("support trace candidate_ref mismatch")
    if trace.interpretation_ref != candidate.interpretation.interpretation_ref:
        raise KnowledgeGateError("support trace interpretation_ref mismatch")
    if (
        trace.statement.statement_ref
        != candidate.interpretation.statement.statement_ref
    ):
        raise KnowledgeGateError(
            "support trace Statement is not the Statement interpreted by the candidate"
        )

    expected_resolution_refs = tuple(
        item.resolution_ref for item in construction.identity_resolutions
    )
    if trace.identity_resolution_refs != expected_resolution_refs:
        raise KnowledgeGateError(
            "support trace must preserve the identity resolutions used by construction"
        )

    # Accessing these properties proves the typed chain exists without copying it.
    if trace.passage is not trace.statement.passage:
        raise KnowledgeGateError("support trace Passage lineage is invalid")
    if trace.artifact is not trace.passage.artifact:
        raise KnowledgeGateError("support trace Artifact lineage is invalid")
    if trace.observation is not trace.artifact.observation:
        raise KnowledgeGateError("support trace Observation lineage is invalid")
    if trace.source is not trace.observation.source:
        raise KnowledgeGateError("support trace Source lineage is invalid")

    validate_candidate(
        KnowledgeCandidate(
            construction.proposition,
            supports=(support,),
            expected_fingerprint=construction.proposition.fingerprint,
        )
    )
    return support
