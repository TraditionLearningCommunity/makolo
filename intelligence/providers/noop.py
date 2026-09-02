from intelligence.contracts import IntelligenceRequest, IntelligenceResult

from .base import IntelligenceProvider


class NoOpIntelligenceProvider(IntelligenceProvider):
    key = "noop"

    def execute(self, request: IntelligenceRequest) -> IntelligenceResult:
        return IntelligenceResult.unavailable("provider_not_configured")
