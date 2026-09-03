from enum import Enum


class IntelligenceCapability(str, Enum):
    TEXT_GENERATE = "text_generate"
    STRUCTURED_GENERATE = "structured_generate"
    EMBED = "embed"
    RERANK = "rerank"
