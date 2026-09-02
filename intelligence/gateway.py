from __future__ import annotations

from .contracts import IntelligenceRequest, IntelligenceResult
from .exceptions import IntelligenceError
from .registry import IntelligenceRegistry, get_intelligence_registry


class IntelligenceGateway:
    def __init__(self, registry: IntelligenceRegistry | None = None):
        self.registry = registry or get_intelligence_registry()

    def execute(self, request: IntelligenceRequest) -> IntelligenceResult:
        providers = self.registry.providers_for(request.capability)
        if not providers:
            return IntelligenceResult.unavailable("capability_not_configured")

        last_reason = "provider_unavailable"
        for provider in providers:
            try:
                result = provider.execute(request)
            except IntelligenceError as exc:
                last_reason = exc.__class__.__name__
                continue
            if result.available:
                return result
            last_reason = result.reason or last_reason
        return IntelligenceResult.unavailable(last_reason)


def get_intelligence_gateway() -> IntelligenceGateway:
    return IntelligenceGateway()
