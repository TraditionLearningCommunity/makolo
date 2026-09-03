from __future__ import annotations

from dataclasses import replace
from time import monotonic

from .contracts import IntelligenceRequest, IntelligenceResult
from .exceptions import IntelligenceError, InvalidProviderResult
from .registry import IntelligenceRegistry, get_intelligence_registry
from .telemetry import record_invocation


def _feature(request: IntelligenceRequest) -> str:
    value = request.metadata.get("feature", "")
    return value if isinstance(value, str) else ""


class IntelligenceGateway:
    def __init__(self, registry: IntelligenceRegistry | None = None):
        self.registry = registry or get_intelligence_registry()

    def execute(self, request: IntelligenceRequest) -> IntelligenceResult:
        providers = self.registry.providers_for(request.capability)
        if not providers:
            record_invocation(
                capability=request.capability.value,
                available=False,
                reason="capability_not_configured",
                feature=_feature(request),
            )
            return IntelligenceResult.unavailable("capability_not_configured")

        last_reason = "provider_unavailable"
        for provider in providers:
            started_at = monotonic()
            try:
                result = provider.execute(request)
            except IntelligenceError as exc:
                last_reason = exc.__class__.__name__
                record_invocation(
                    capability=request.capability.value,
                    available=False,
                    provider_key=provider.key,
                    reason=last_reason,
                    latency_ms=round((monotonic() - started_at) * 1000),
                    feature=_feature(request),
                )
                continue

            if not isinstance(result, IntelligenceResult):
                last_reason = InvalidProviderResult.__name__
                record_invocation(
                    capability=request.capability.value,
                    available=False,
                    provider_key=provider.key,
                    reason=last_reason,
                    latency_ms=round((monotonic() - started_at) * 1000),
                    feature=_feature(request),
                )
                continue

            if result.available:
                if not result.provider_key:
                    result = replace(result, provider_key=provider.key)
                record_invocation(
                    capability=request.capability.value,
                    available=True,
                    provider_key=result.provider_key,
                    model=result.model,
                    latency_ms=round((monotonic() - started_at) * 1000),
                    feature=_feature(request),
                )
                return result

            last_reason = result.reason or last_reason
            record_invocation(
                capability=request.capability.value,
                available=False,
                provider_key=result.provider_key or provider.key,
                model=result.model,
                reason=last_reason,
                latency_ms=round((monotonic() - started_at) * 1000),
                feature=_feature(request),
            )

        return IntelligenceResult.unavailable(last_reason)


def get_intelligence_gateway() -> IntelligenceGateway:
    return IntelligenceGateway()
