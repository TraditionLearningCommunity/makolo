from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from django.core.exceptions import ValidationError

from organizations.models import Organization, TeamMembership, TeamMembershipStatus


@dataclass(frozen=True)
class UsageMeasurement:
    value: int | float
    provider: str


_USAGE_PROVIDERS: dict[str, Callable] = {}


def register_usage_provider(key):
    def decorator(func):
        if key in _USAGE_PROVIDERS:
            raise RuntimeError(f"Usage provider déjà enregistré: {key}")
        _USAGE_PROVIDERS[key] = func
        return func
    return decorator


@register_usage_provider("organizations.active_team_members")
def active_team_members(subject):
    if not isinstance(subject, Organization):
        raise ValidationError("organizations.active_team_members attend un Space.")
    count = (
        TeamMembership.objects.filter(
            team__organization=subject,
            team__is_active=True,
            status=TeamMembershipStatus.ACTIVE,
        )
        .values("user_id")
        .distinct()
        .count()
    )
    return UsageMeasurement(value=count, provider="organizations.active_team_members")


def measure_feature_usage(feature, subject):
    if not feature.usage_provider:
        return None
    provider = _USAGE_PROVIDERS.get(feature.usage_provider)
    if provider is None:
        raise ValidationError(f"Usage provider inconnu: {feature.usage_provider}")
    return provider(subject)
