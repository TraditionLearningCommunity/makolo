from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .capabilities import IntelligenceCapability


@dataclass(frozen=True, slots=True)
class IntelligenceRequest:
    capability: IntelligenceCapability
    input: Mapping[str, Any]
    schema: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntelligenceResult:
    available: bool
    output: Any = None
    provider_key: str = ""
    model: str = ""
    reason: str = ""

    @classmethod
    def unavailable(cls, reason: str = "provider_unavailable") -> "IntelligenceResult":
        return cls(available=False, reason=reason)


@dataclass(frozen=True, slots=True)
class RerankItem:
    key: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RerankOutput:
    keys: Sequence[str]
