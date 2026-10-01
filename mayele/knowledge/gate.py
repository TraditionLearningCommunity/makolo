from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from mayele.common.errors import KnowledgeGateError
from .contracts import (
    KnowledgeSupport,
    Proposition,
    PropositionKind,
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
