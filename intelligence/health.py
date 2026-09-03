from __future__ import annotations

from time import monotonic

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone

from .capabilities import IntelligenceCapability
from .contracts import IntelligenceRequest
from .credentials import get_provider_secret
from .exceptions import IntelligenceError, ProviderUnavailable
from .models import (
    ProviderConnection,
    ProviderHealth,
    ProviderProtocol,
    ProviderScope,
    _validate_external_provider_url,
)
from .providers.openai_compatible import OpenAICompatibleProvider


def test_provider_connection(connection: ProviderConnection) -> str:
    started = monotonic()
    status = ProviderHealth.UNKNOWN
    try:
        if connection.scope in {ProviderScope.SPACE, ProviderScope.PROFILE}:
            _validate_external_provider_url(connection.base_url)
        secret = get_provider_secret(connection=connection)
        if connection.protocol != ProviderProtocol.OPENAI_COMPATIBLE:
            status = ProviderHealth.UNAVAILABLE
        else:
            provider = OpenAICompatibleProvider(
                key=str(connection.pk),
                base_url=connection.base_url,
                api_key=secret,
                model=connection.default_model,
                timeout_seconds=connection.timeout_seconds,
            )
            provider.execute(
                IntelligenceRequest(
                    capability=IntelligenceCapability.TEXT_GENERATE,
                    input={"messages": [{"role": "user", "content": "Reply with OK."}]},
                )
            )
            status = ProviderHealth.HEALTHY
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
