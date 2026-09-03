from __future__ import annotations

from abc import ABC, abstractmethod

from intelligence.capabilities import IntelligenceCapability
from intelligence.contracts import IntelligenceRequest, IntelligenceResult


class IntelligenceProvider(ABC):
    key = "provider"
    capabilities: frozenset[IntelligenceCapability] = frozenset()

    def supports(self, capability: IntelligenceCapability) -> bool:
        return capability in self.capabilities

    @abstractmethod
    def execute(self, request: IntelligenceRequest) -> IntelligenceResult:
        raise NotImplementedError
