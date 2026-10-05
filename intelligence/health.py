from __future__ import annotations

from time import monotonic

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone

from research_missions import ResearchFamily, ResearchMission, ResearchOrigin, ResearchOriginKind

from .capabilities import IntelligenceCapability
from .contracts import IntelligenceRequest
from .credentials import get_provider_secret
from .exceptions import IntelligenceError, ProviderUnavailable
from .models import (
    ProviderConnection,
    ProviderHealth,
    ProviderScope,
    _validate_external_provider_url,
)
from .provider_factory import build_configured_provider


def test_provider_connection(connection: ProviderConnection) -> str:
    started = monotonic()
    status = ProviderHealth.UNKNOWN
    try:
        if connection.scope in {ProviderScope.SPACE, ProviderScope.PROFILE}:
            _validate_external_provider_url(connection.base_url)
        secret = get_provider_secret(connection=connection)
        provider = build_configured_provider(
            connection=connection,
            secret=secret,
            model=connection.default_model,
        )
        if provider is None:
            status = ProviderHealth.UNAVAILABLE
        elif provider.supports(IntelligenceCapability.TEXT_GENERATE):
            provider.execute(
                IntelligenceRequest(
                    capability=IntelligenceCapability.TEXT_GENERATE,
                    input={"messages": [{"role": "user", "content": "Reply with OK."}]},
                )
            )
            status = ProviderHealth.HEALTHY
        elif provider.supports(IntelligenceCapability.WEB_RESEARCH):
            mission = ResearchMission(
                primary_family=ResearchFamily.REFERENCE,
                subject="Makolo provider connectivity",
                questions=("Find one public source about Makolo.",),
                origins=(
                    ResearchOrigin(
                        kind=ResearchOriginKind.INITIAL,
                        source_ref="intelligence:provider-healthcheck",
                    ),
                ),
                reasons=("Verify explicit Web Research provider connectivity.",),
                limits={"max_candidates": 1, "max_queries": 1},
            )
            provider.execute(
                IntelligenceRequest(
                    capability=IntelligenceCapability.WEB_RESEARCH,
                    input={
                        "request": {
                            "contract_version": 1,
                            "request_ref": "provider-healthcheck",
                            "mode": "discover",
                            "requested_at": timezone.now().isoformat(),
                            "mission": dict(mission.to_provenance_payload()),
                        }
                    },
                    metadata={"feature": "provider_healthcheck"},
                )
            )
            status = ProviderHealth.HEALTHY
        else:
            status = ProviderHealth.UNAVAILABLE
    except ProviderUnavailable as exc:
        status = (
            ProviderHealth.INVALID_CREDENTIALS
            if str(exc) == "invalid_credentials"
            else ProviderHealth.UNAVAILABLE
        )
    except (IntelligenceError, ValidationError, ValueError, ImproperlyConfigured):
        status = ProviderHealth.UNAVAILABLE

    connection.health_status = status
    connection.last_checked_at = timezone.now()
    connection.last_latency_ms = max(0, int((monotonic() - started) * 1000))
    connection.save(update_fields=["health_status", "last_checked_at", "last_latency_ms", "updated_at"])
    return status
