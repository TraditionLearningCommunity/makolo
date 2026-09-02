from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

from .capabilities import IntelligenceCapability
from .credentials import get_provider_secret
from .models import IntelligenceRoute, ProviderHealth, ProviderProtocol, ProviderScope
from .providers.openai_compatible import OpenAICompatibleProvider
from .registry import IntelligenceRegistry


def _scope_filter(*, space=None, profile=None):
    query = Q(connection__scope=ProviderScope.PLATFORM)
    if space is not None:
        query |= Q(connection__scope=ProviderScope.SPACE, connection__space=space)
    if profile is not None:
        query |= Q(connection__scope=ProviderScope.PROFILE, connection__profile=profile)
    return query


def build_runtime_registry(*, capability: IntelligenceCapability, space=None, profile=None) -> IntelligenceRegistry:
    routes = (
        IntelligenceRoute.objects.select_related("connection", "connection__credential")
        .filter(capability=capability.value, enabled=True, connection__enabled=True)
        .filter(_scope_filter(space=space, profile=profile))
        .exclude(connection__health_status__in=[ProviderHealth.UNAVAILABLE, ProviderHealth.INVALID_CREDENTIALS])
        .order_by("priority", "connection__priority", "id")
    )
    providers = []
    for route in routes:
        connection = route.connection
        try:
            secret = get_provider_secret(connection=connection)
        except (ValueError, ImproperlyConfigured):
            continue
        model = route.model.strip() or connection.default_model
        if connection.protocol == ProviderProtocol.OPENAI_COMPATIBLE:
            providers.append(
                OpenAICompatibleProvider(
                    key=str(connection.pk),
                    base_url=connection.base_url,
                    api_key=secret,
                    model=model,
                    timeout_seconds=connection.timeout_seconds,
                )
            )
    return IntelligenceRegistry(providers=providers)
