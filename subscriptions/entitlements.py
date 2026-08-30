from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from organizations.models import Organization

from .contracts import (
    EntitlementAggregationStrategy,
    EntitlementSourceType,
    FeatureEnforcementPolicy,
    FeatureValueType,
    SubscriptionItemStatus,
    SubscriptionPlanType,
    SubscriptionSubjectType,
)
from .models import FeatureDefinition, PlanEntitlement
from .runtime_models import EntitlementGrant, SubscriptionItem
from .selectors import get_subscription_for_subject
from .usage import measure_feature_usage


@dataclass(frozen=True)
class EntitlementSource:
    source_type: str
    source_id: str
    value: Any
    plan_code: str | None = None
    plan_version: int | None = None


@dataclass(frozen=True)
class EffectiveEntitlementResult:
    feature_code: str
    effective_value: Any
    sources: tuple[EntitlementSource, ...]
    usage: Any = None
    remaining: Any = None
    allowed: bool = False
    over_limit: bool = False
    reason_code: str = "not_entitled"


def _subject_type(subject):
    User = get_user_model()
    if isinstance(subject, User):
        return SubscriptionSubjectType.PROFILE
    if isinstance(subject, Organization):
        return SubscriptionSubjectType.SPACE
    raise ValidationError("Le sujet doit être un Profile ou un Space canonique.")


def _numeric(value):
    return Decimal(str(value))


def _render_numeric(feature, value):
    if feature.value_type == FeatureValueType.INTEGER:
        return int(value)
    return format(value.normalize(), "f")


def _aggregate(feature, contributions):
    values = [entry["source"].value for entry in contributions]
    strategy = feature.aggregation_strategy
    if strategy == EntitlementAggregationStrategy.BOOLEAN_OR:
        return any(values)
    if strategy == EntitlementAggregationStrategy.SUM:
        return _render_numeric(feature, sum((_numeric(value) for value in values), Decimal("0")))
    if strategy == EntitlementAggregationStrategy.MAX:
        return _render_numeric(feature, max(_numeric(value) for value in values))
    if strategy == EntitlementAggregationStrategy.REPLACE:
        winner = max(contributions, key=lambda entry: (entry["priority"], entry["at"], entry["source"].source_id))
        return winner["source"].value
    raise ValidationError(f"Stratégie d'agrégation inconnue: {strategy}")


def _decorate_usage(feature, subject, effective_value, sources):
    if effective_value is None:
        return EffectiveEntitlementResult(feature.code, None, sources)

    if feature.enforcement_policy == FeatureEnforcementPolicy.FEATURE_GATE:
        allowed = bool(effective_value)
        return EffectiveEntitlementResult(
            feature_code=feature.code,
            effective_value=effective_value,
            sources=sources,
            allowed=allowed,
            reason_code="allowed" if allowed else "feature_disabled",
        )

    measurement = measure_feature_usage(feature, subject)
    if measurement is None:
        return EffectiveEntitlementResult(
            feature_code=feature.code,
            effective_value=effective_value,
            sources=sources,
            allowed=True,
            reason_code="allowed",
        )

    limit = _numeric(effective_value)
    usage = _numeric(measurement.value)
    remaining_decimal = max(limit - usage, Decimal("0"))
    over_limit = usage > limit
    allowed = usage < limit
    if feature.value_type == FeatureValueType.INTEGER:
        usage_value = int(usage)
        remaining = int(remaining_decimal)
    else:
        usage_value = format(usage.normalize(), "f")
        remaining = format(remaining_decimal.normalize(), "f")
    reason = "over_limit" if over_limit else ("limit_reached" if usage == limit else "allowed")
    return EffectiveEntitlementResult(
        feature_code=feature.code,
        effective_value=effective_value,
        sources=sources,
        usage=usage_value,
        remaining=remaining,
        allowed=allowed,
        over_limit=over_limit,
        reason_code=reason,
    )


def _resolve(subject, *, feature_code=None, at=None):
    at = at or timezone.now()
    subject_type = _subject_type(subject)
    subscription = get_subscription_for_subject(subject)

    feature_qs = FeatureDefinition.objects.filter(is_active=True)
    if subject_type == SubscriptionSubjectType.PROFILE:
        feature_qs = feature_qs.filter(supports_profile=True)
    else:
        feature_qs = feature_qs.filter(supports_space=True)
    if feature_code is not None:
        feature_qs = feature_qs.filter(code=feature_code)
    features = {feature.code: feature for feature in feature_qs}

    contributions = {code: [] for code in features}
    if subscription is not None:
        items = (
            SubscriptionItem.objects.filter(
                subscription=subscription,
                status=SubscriptionItemStatus.ACTIVE,
                starts_at__lte=at,
            )
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))
            .select_related("plan", "plan_version")
        )
        item_by_version = {item.plan_version_id: item for item in items}
        entitlements = PlanEntitlement.objects.filter(
            plan_version_id__in=item_by_version,
            feature__code__in=features,
            feature__is_active=True,
        ).select_related("feature")
        for entitlement in entitlements:
            item = item_by_version[entitlement.plan_version_id]
            source_type = (
                EntitlementSourceType.BASE
                if item.item_type == SubscriptionPlanType.BASE
                else EntitlementSourceType.ADDON
            )
            contributions[entitlement.feature.code].append(
                {
                    "priority": 1 if source_type == EntitlementSourceType.BASE else 2,
                    "at": item.starts_at,
                    "source": EntitlementSource(
                        source_type=source_type,
                        source_id=str(item.pk),
                        value=entitlement.value,
                        plan_code=item.plan.code,
                        plan_version=item.plan_version.version,
                    ),
                }
            )

    grant_filter = Q(profile=subject) if subject_type == SubscriptionSubjectType.PROFILE else Q(space=subject)
    grants = (
        EntitlementGrant.objects.filter(grant_filter, feature__code__in=features, feature__is_active=True, revoked_at__isnull=True)
        .filter(valid_from__lte=at)
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=at))
        .select_related("feature")
    )
    for grant in grants:
        contributions[grant.feature.code].append(
            {
                "priority": 3,
                "at": grant.granted_at,
                "source": EntitlementSource(
                    source_type=EntitlementSourceType.GRANT,
                    source_id=str(grant.pk),
                    value=grant.value,
                ),
            }
        )

    results = {}
    for code, feature in features.items():
        entries = sorted(
            contributions[code],
            key=lambda entry: (entry["priority"], entry["at"], entry["source"].source_id),
        )
        sources = tuple(entry["source"] for entry in entries)
        effective = _aggregate(feature, entries) if entries else None
        results[code] = _decorate_usage(feature, subject, effective, sources)
    return results


def resolve_effective_entitlements(subject, *, at=None):
    return _resolve(subject, at=at)


def resolve_entitlement(subject, feature_code, *, at=None):
    results = _resolve(subject, feature_code=feature_code, at=at)
    if feature_code not in results:
        feature = FeatureDefinition.objects.filter(code=feature_code).first()
        if feature is None:
            raise ValidationError({"feature_code": "Feature inconnue."})
        raise ValidationError({"feature_code": "Cette Feature ne supporte pas ce type de sujet ou est inactive."})
    return results[feature_code]
