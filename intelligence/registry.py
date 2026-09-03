from __future__ import annotations

from dataclasses import dataclass, field

from .capabilities import IntelligenceCapability
from .providers.base import IntelligenceProvider
from .providers.noop import NoOpIntelligenceProvider


@dataclass(slots=True)
class IntelligenceRegistry:
    providers: list[IntelligenceProvider] = field(default_factory=list)

    def register(self, provider: IntelligenceProvider) -> None:
        self.providers.append(provider)

    def providers_for(self, capability: IntelligenceCapability) -> list[IntelligenceProvider]:
        return [provider for provider in self.providers if provider.supports(capability)]


_default_registry = IntelligenceRegistry(providers=[NoOpIntelligenceProvider()])


def get_intelligence_registry() -> IntelligenceRegistry:
    return _default_registry


def set_intelligence_registry(registry: IntelligenceRegistry) -> None:
    global _default_registry
    _default_registry = registry


def reset_intelligence_registry() -> None:
    set_intelligence_registry(IntelligenceRegistry(providers=[NoOpIntelligenceProvider()]))
