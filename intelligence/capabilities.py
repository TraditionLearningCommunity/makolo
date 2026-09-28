from enum import Enum


class IntelligenceCapability(str, Enum):
    TEXT_GENERATE = "text_generate"
    STRUCTURED_GENERATE = "structured_generate"
    EMBED = "embed"
    RERANK = "rerank"
    WEB_RESEARCH = "web_research"


# These are the capabilities currently configurable through the persisted
# IntelligenceRoute model. WEB_RESEARCH is intentionally runtime-only in Phase 2
# so adding the execution capability does not create a migration before routing
# and provider protocol persistence are designed deliberately.
PERSISTED_INTELLIGENCE_ROUTE_CAPABILITIES = (
    IntelligenceCapability.TEXT_GENERATE,
    IntelligenceCapability.STRUCTURED_GENERATE,
    IntelligenceCapability.EMBED,
    IntelligenceCapability.RERANK,
)
