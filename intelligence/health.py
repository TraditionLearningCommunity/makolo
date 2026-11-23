from __future__ import annotations

from time import monotonic

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone

from research_missions import ResearchFamily, ResearchMission, ResearchOrigin, ResearchOriginKind

from .capabilities import IntelligenceCapability
from .contracts import IntelligenceRequest, IntelligenceResult
from .credentials import get_provider_secret
from .exceptions import IntelligenceError, ProviderUnavailable
from .models import (
    ProviderConnection,
    ProviderHealth,
    ProviderScope,
    _validate_external_provider_url,
)
from .provider_factory import build_configured_provider


def _result_health(result) -> str:
    """A returned unavailable result is not a successful health probe."""
    if not isinstance(result, IntelligenceResult):
        return ProviderHealth.UNAVAILABLE
    if result.available:
        return ProviderHealth.HEALTHY
    if result.reason == "invalid_credentials":
        return ProviderHealth.INVALID_CREDENTIALS
    return ProviderHealth.UNAVAILABLE


def test_provider_connection(connection: ProviderConnection) -> str:
    started = monotonic()
    # A health probe may outlive a key rotation, disable or disconnect. Keep
    # the exact row version observed before contacting the external provider.
    original_updated_at = connection.updated_at
    original_enabled = connection.enabled
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
            result = provider.execute(
                IntelligenceRequest(
                    capability=IntelligenceCapability.TEXT_GENERATE,
                    input={"messages": [{"role": "user", "content": "Reply with OK."}]},
                )
            )
            status = _result_health(result)
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
            result = provider.execute(
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
            status = _result_health(result)
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

    # Compare-and-swap: do not overwrite fresh state after rotation, disable,
    # or removal while a billable provider probe was in flight. QuerySet.update
    # avoids an unconditional model.save() that could revive stale evidence.
    checked_at = timezone.now()
    latency = max(0, int((monotonic() - started) * 1000))
    updated = ProviderConnection.objects.filter(
        pk=connection.pk,
        enabled=original_enabled,
        updated_at=original_updated_at,
    ).update(
        health_status=status,
        last_checked_at=checked_at,
        last_latency_ms=latency,
        updated_at=checked_at,
    )
    if updated:
        connection.health_status = status
        connection.last_checked_at = checked_at
        connection.last_latency_ms = latency
        connection.updated_at = checked_at
        return status
    # The caller must not announce a result for an obsolete credential.
    return ProviderHealth.UNKNOWN
