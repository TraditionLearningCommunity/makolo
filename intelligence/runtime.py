from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models import Q

from .capabilities import IntelligenceCapability
from .credentials import get_provider_secret
from .models import (
    IntelligenceRoute,
    ProviderHealth,
    ProviderScope,
    _validate_external_provider_url,
)
from .provider_factory import build_configured_provider
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
        if connection.scope in {ProviderScope.SPACE, ProviderScope.PROFILE}:
            try:
                _validate_external_provider_url(connection.base_url)
            except ValidationError:
                continue
        try:
            secret = get_provider_secret(connection=connection)
        except (ValueError, ImproperlyConfigured):
            continue
        model = route.model.strip() or connection.default_model
        provider = build_configured_provider(
            connection=connection,
            secret=secret,
            model=model,
        )
        if provider is not None and provider.supports(capability):
            providers.append(provider)
    return IntelligenceRegistry(providers=providers)
