"""Provider-neutral contracts for Makolo Web Research execution."""

from .contracts import (
    WEB_RESEARCH_CONTRACT_VERSION,
    WebResearchCandidate,
    WebResearchContractError,
    WebResearchMode,
    WebResearchOutcome,
    WebResearchRequest,
    WebResearchResult,
    WebResearchSource,
    WebResearchStopReason,
    make_web_research_candidate_ref,
    make_web_research_source_ref,
)
from .discovery import (
    DISCOVERY_OUTPUT_CONTRACT_VERSION,
    DiscoveryKnowledgePort,
    DiscoveryKnowledgeState,
    DiscoveryKnownRef,
    DiscoveryLookup,
    DiscoveryNormalizer,
    DiscoveryOutput,
    DiscoveryRecord,
)
from .intelligence_engine import IntelligenceWebResearchEngine
from .ports import WebResearchEnginePort

__all__ = [
    "WEB_RESEARCH_CONTRACT_VERSION",
    "WebResearchCandidate",
    "WebResearchContractError",
    "WebResearchEnginePort",
    "IntelligenceWebResearchEngine",
    "DISCOVERY_OUTPUT_CONTRACT_VERSION",
    "DiscoveryKnowledgePort",
    "DiscoveryKnowledgeState",
    "DiscoveryKnownRef",
    "DiscoveryLookup",
    "DiscoveryNormalizer",
    "DiscoveryOutput",
    "DiscoveryRecord",
    "WebResearchMode",
    "WebResearchOutcome",
    "WebResearchRequest",
    "WebResearchResult",
    "WebResearchSource",
    "WebResearchStopReason",
    "make_web_research_candidate_ref",
    "make_web_research_source_ref",
]
