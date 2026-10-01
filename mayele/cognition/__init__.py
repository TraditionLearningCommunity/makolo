"""Framework-independent Mayele cognition contracts."""

from .contracts import (
    CandidateStatus,
    ConditionCandidate,
    Interpretation,
    InterpretationMode,
    InterpretationReferent,
    InterpretationTransformation,
    PropertyCandidate,
    RealityCandidate,
    ReferentKind,
    RelationCandidate,
    RelationCandidateParticipant,
    WorldCandidate,
)
from .gate import CognitionCandidate, validate_candidate, validate_interpretation

__all__ = [
    "CandidateStatus",
    "CognitionCandidate",
    "ConditionCandidate",
    "Interpretation",
    "InterpretationMode",
    "InterpretationReferent",
    "InterpretationTransformation",
    "PropertyCandidate",
    "RealityCandidate",
    "ReferentKind",
    "RelationCandidate",
    "RelationCandidateParticipant",
    "WorldCandidate",
    "validate_candidate",
    "validate_interpretation",
]
