from enum import StrEnum


class IntelligenceCapability(StrEnum):
    TEXT_GENERATE = "text_generate"
    STRUCTURED_GENERATE = "structured_generate"
    EMBED = "embed"
    RERANK = "rerank"
