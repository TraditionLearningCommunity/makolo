from __future__ import annotations

from .models import ProviderProtocol
from .providers.exa_web import ExaWebResearchProvider
from .providers.openai_compatible import OpenAICompatibleProvider
from .providers.openai_responses_web import OpenAIResponsesWebResearchProvider
from .providers.tavily_web import TavilyWebResearchProvider


def build_configured_provider(*, connection, secret: str, model: str = ""):
    common = {
        "key": str(connection.pk),
        "base_url": connection.base_url,
        "api_key": secret,
        "timeout_seconds": connection.timeout_seconds,
    }
    if connection.protocol == ProviderProtocol.OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(model=model, **common)
    if connection.protocol == ProviderProtocol.OPENAI_RESPONSES_WEB:
        return OpenAIResponsesWebResearchProvider(model=model, **common)
    if connection.protocol == ProviderProtocol.TAVILY_SEARCH:
        return TavilyWebResearchProvider(**common)
    if connection.protocol == ProviderProtocol.EXA_SEARCH:
        return ExaWebResearchProvider(**common)
    return None
