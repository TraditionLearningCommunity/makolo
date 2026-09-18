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
    ExpansionContractError,
    ObservationContractError,
    ProspectorContractError,
    UnsupportedTargetKindError,
)
from .frontier import FrontierClaim, FrontierState
from .expansion import ExpansionPolicy, ExpansionResult, ObservationExpansionSink
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
from .policy import BudgetPolicy, GateDecision, GateDisposition, ObservationPolicy
from .runtime import ProspectorRuntime, RuntimeCycleStats, RuntimePolicy
from .security import ObservationGate
from .safe_handoff import SafeHandoffResult, SafeObservationHandoff

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
    "BudgetPolicy",
    "ObservationPolicy",
    "GateDecision",
    "GateDisposition",
    "ObservationGate",
    "SafeHandoffResult",
    "SafeObservationHandoff",
    "RuntimePolicy",
    "RuntimeCycleStats",
    "ProspectorRuntime",
    "ProspectorContractError",
    "UnsupportedTargetKindError",
    "FrontierConflictError",
    "FrontierClaimError",
    "ObservationContractError",
    "ExpansionContractError",
    "ExpansionPolicy",
    "ExpansionResult",
    "ObservationExpansionSink",
]
