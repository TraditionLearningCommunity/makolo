"""Framework-independent contracts for bounded internal Makolo research needs."""

from .contracts import (
    RESEARCH_MISSION_CONTRACT_VERSION,
    ResearchContext,
    ResearchFamily,
    ResearchMission,
    ResearchMissionCandidate,
    ResearchMissionContractError,
    ResearchOrigin,
    ResearchOriginKind,
)
from .ports import ResearchContextSourcePort

__all__ = [
    "RESEARCH_MISSION_CONTRACT_VERSION",
    "ResearchContext",
    "ResearchContextSourcePort",
    "ResearchFamily",
    "ResearchMission",
    "ResearchMissionCandidate",
    "ResearchMissionContractError",
    "ResearchOrigin",
    "ResearchOriginKind",
]
