from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mayele.common.errors import MayeleContractError
from mayele.observation import Mention

from .contracts import (
    ConditionCandidate,
    Interpretation,
    InterpretationReferent,
    PropertyCandidate,
    RealityCandidate,
    ReferentKind,
    RelationCandidate,
    WorldCandidate,
)


@dataclass(frozen=True, slots=True)
class CognitionCandidate:
    candidate: WorldCandidate
    expected_fingerprint: Optional[str] = None


def validate_interpretation(interpretation: Interpretation) -> Interpretation:
    """Validate MY3 technical lineage without assessing world truth."""

    if not isinstance(interpretation, Interpretation):
        raise MayeleContractError("interpretation must be Interpretation")
    if not interpretation.statement.statement_ref:
        raise MayeleContractError("interpretation requires a source statement")

    mention_refs = set()
    for mention in interpretation.mentions:
        if not isinstance(mention, Mention):
            raise MayeleContractError("interpretation mentions must be Mention values")
        if mention.statement.statement_ref != interpretation.statement.statement_ref:
            raise MayeleContractError(
                "interpretation mention belongs to a different statement"
            )
        if mention.mention_ref in mention_refs:
            raise MayeleContractError("interpretation mentions must be unique")
        mention_refs.add(mention.mention_ref)

    return interpretation


def _validate_referent(
    interpretation: Interpretation,
    referent: InterpretationReferent,
) -> None:
    if not isinstance(referent, InterpretationReferent):
        raise MayeleContractError("candidate referent must be InterpretationReferent")

    if referent.kind is ReferentKind.MENTION:
        known_mentions = {item.mention_ref for item in interpretation.mentions}
        if referent.ref not in known_mentions:
            raise MayeleContractError(
                "mention referent must be present in interpretation lineage"
            )


def validate_candidate(candidate: CognitionCandidate) -> WorldCandidate:
    """Pure MY3 gate. It checks structure, lineage and scope only."""

    if not isinstance(candidate, CognitionCandidate):
        raise MayeleContractError("candidate must be CognitionCandidate")

    world_candidate = candidate.candidate
    if not isinstance(
        world_candidate,
        (
            RealityCandidate,
            PropertyCandidate,
            RelationCandidate,
            ConditionCandidate,
        ),
    ):
        raise MayeleContractError("unsupported cognition candidate type")

    interpretation = validate_interpretation(world_candidate.interpretation)

    if isinstance(world_candidate, RealityCandidate):
        if world_candidate.source_referent is not None:
            _validate_referent(interpretation, world_candidate.source_referent)
    elif isinstance(world_candidate, PropertyCandidate):
        _validate_referent(interpretation, world_candidate.subject)
    elif isinstance(world_candidate, RelationCandidate):
        for participant in world_candidate.participants:
            _validate_referent(interpretation, participant.referent)
    else:
        for referent in world_candidate.referents:
            _validate_referent(interpretation, referent)

    if (
        candidate.expected_fingerprint is not None
        and candidate.expected_fingerprint != world_candidate.fingerprint
    ):
        raise MayeleContractError("candidate fingerprint mismatch")

    return world_candidate
