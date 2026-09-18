"""Makolo Prospecteur core contracts.

The import surface is deliberately framework-independent. Django, PostgreSQL,
Crawlee and provider integrations live behind adapters/ports.
"""

from .contracts import (
    CONTRACT_VERSION,
    ProspectingCandidate,
    ProspectingEvidence,
    ProspectingTarget,
)
from .errors import (
    FrontierClaimError,
    FrontierConflictError,
    ObservationContractError,
    ProspectorContractError,
    UnsupportedTargetKindError,
)
from .frontier import FrontierClaim, FrontierState
from .observation_contracts import (
    OBSERVATION_CONTRACT_VERSION,
    ObservationDisposition,
    ObservationReceipt,
    ObservationReport,
    ObservationStatus,
    ObservationTarget,
    ObservedReference,
    make_handoff_key,
    observation_target_from_claim,
)

__all__ = [
    "CONTRACT_VERSION",
    "OBSERVATION_CONTRACT_VERSION",
    "ProspectingCandidate",
    "ProspectingEvidence",
    "ProspectingTarget",
    "FrontierClaim",
    "FrontierState",
    "ObservationTarget",
    "ObservationReceipt",
    "ObservationReport",
    "ObservedReference",
    "ObservationDisposition",
    "ObservationStatus",
    "make_handoff_key",
    "observation_target_from_claim",
    "ProspectorContractError",
    "UnsupportedTargetKindError",
    "FrontierConflictError",
    "FrontierClaimError",
    "ObservationContractError",
]
