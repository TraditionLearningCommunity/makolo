from enum import Enum


class IntelligenceCapability(str, Enum):
    TEXT_GENERATE = "text_generate"
    STRUCTURED_GENERATE = "structured_generate"
    EMBED = "embed"
    RERANK = "rerank"
    WEB_RESEARCH = "web_research"


PERSISTED_INTELLIGENCE_ROUTE_CAPABILITIES = (
    IntelligenceCapability.TEXT_GENERATE,
    IntelligenceCapability.STRUCTURED_GENERATE,
    IntelligenceCapability.EMBED,
    IntelligenceCapability.RERANK,
    IntelligenceCapability.WEB_RESEARCH,
)
