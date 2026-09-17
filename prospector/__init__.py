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
    ProspectorContractError,
    UnsupportedTargetKindError,
)
from .frontier import FrontierClaim, FrontierState

__all__ = [
    "CONTRACT_VERSION",
    "ProspectingCandidate",
    "ProspectingEvidence",
    "ProspectingTarget",
    "FrontierClaim",
    "FrontierState",
    "ProspectorContractError",
    "UnsupportedTargetKindError",
    "FrontierConflictError",
    "FrontierClaimError",
]
