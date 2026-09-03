from intelligence.capabilities import IntelligenceCapability
from intelligence.contracts import IntelligenceRequest, IntelligenceResult

from .base import IntelligenceProvider


class NoOpIntelligenceProvider(IntelligenceProvider):
    key = "noop"
    capabilities = frozenset(IntelligenceCapability)

    def execute(self, request: IntelligenceRequest) -> IntelligenceResult:
        return IntelligenceResult.unavailable("provider_not_configured")
