from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Q
from django.utils import timezone

from requirements.contracts import RequirementMode

from .contracts import (
    FeatureValueType,
    RequirementPhase,
    SubscriptionItemStatus,
    SubscriptionPlanType,
    SubscriptionTransitionKind,
)
from .eligibility import PlanEligibilityResult, resolve_plan_eligibility
from .eligibility_models import PlanRequirement
from .entitlements import _aggregate
from .models import FeatureDefinition, PlanEntitlement, PlanVersion
from .runtime_models import EntitlementGrant, Subscription, SubscriptionItem
from .usage import measure_feature_usage


@dataclass(frozen=True)
class SubscriptionQuotaChange:
    feature_code: str
    current_value: Any
    target_value: Any
    usage: Any
    over_limit_after_change: bool


@dataclass(frozen=True)
class SubscriptionChangePreview:
    kind: str
    current_plan_version_id: str | None
    target_plan_version_id: str
    features_gained: tuple[str, ...]
    features_lost: tuple[str, ...]
    quota_changes: tuple[SubscriptionQuotaChange, ...]
    requirement_keys: tuple[str, ...]
    payment_requirement_keys: tuple[str, ...]
    eligibility: PlanEligibilityResult | None
    warnings: tuple[str, ...]


def _source_value(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)) != 0
    if isinstance(value, str):
        try:
            return Decimal(value) != 0
        except Exception:
            return bool(value)
    return bool(value)


def _aggregate_versions(subject, entries, *, at):
    features = {
        feature.pk: feature
        for feature in FeatureDefinition.objects.filter(is_active=True)
    }
    contributions = {feature_id: [] for feature_id in features}
    version_ids = {entry["plan_version_id"] for entry in entries}
    entitlements = PlanEntitlement.objects.filter(
        plan_version_id__in=version_ids,
        feature_id__in=features,
    ).select_related("feature")
    by_version = {}
    for entitlement in entitlements:
        by_version.setdefault(entitlement.plan_version_id, []).append(entitlement)
    for entry in entries:
        priority = 1 if entry["item_type"] == SubscriptionPlanType.BASE else 2
        for entitlement in by_version.get(entry["plan_version_id"], ()): 
            contributions[entitlement.feature_id].append(
                {
                    "priority": priority,
                    "at": entry["at"],
                    "source": type("PreviewSource", (), {"value": entitlement.value, "source_id": entry["source_id"]})(),
                }
            )

    grant_filter = Q(profile=subject) if hasattr(subject, "username") else Q(space=subject)
    grants = (
        EntitlementGrant.objects.filter(grant_filter, feature_id__in=features, revoked_at__isnull=True, valid_from__lte=at)
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=at))
    )
    for grant in grants:
        contributions[grant.feature_id].append(
            {
                "priority": 3,
                "at": grant.granted_at,
                "source": type("PreviewSource", (), {"value": grant.value, "source_id": str(grant.pk)})(),
            }
        )

    values = {}
    for feature_id, feature in features.items():
        rows = contributions[feature_id]
        values[feature.code] = _aggregate(feature, rows) if rows else None
    return features, values


def _active_entries(subscription, *, at):
    items = list(
        SubscriptionItem.objects.filter(
            subscription=subscription,
            status=SubscriptionItemStatus.ACTIVE,
            starts_at__lte=at,
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))
        .select_related("plan", "plan_version")
    )
    entries = [
        {
            "item_id": item.pk,
            "plan_version_id": item.plan_version_id,
            "item_type": item.item_type,
            "at": item.starts_at,
            "source_id": str(item.pk),
        }
        for item in items
    ]
    return items, entries


def preview_subscription_change(
    *,
    subscription,
    kind,
    target_plan_version=None,
    source_item=None,
    request_origin="self_service",
    at=None,
):
    at = at or timezone.now()
    subscription = Subscription.objects.select_related("profile", "space").get(pk=subscription.pk)
    items, current_entries = _active_entries(subscription, at=at)

    if kind == SubscriptionTransitionKind.BASE_SWITCH:
        if target_plan_version is None:
            raise ValueError("base_switch exige une PlanVersion cible.")
        current_item = next((item for item in items if item.item_type == SubscriptionPlanType.BASE), None)
        current_plan_version_id = str(current_item.plan_version_id) if current_item else None
        target = PlanVersion.objects.select_related("plan").get(pk=target_plan_version.pk)
        future_entries = [entry for entry in current_entries if entry["item_type"] != SubscriptionPlanType.BASE]
        future_entries.append({
            "item_id": None,
            "plan_version_id": target.pk,
            "item_type": SubscriptionPlanType.BASE,
            "at": at,
            "source_id": f"preview:{target.pk}",
        })
    elif kind == SubscriptionTransitionKind.ADDON_ADD:
        if target_plan_version is None:
            raise ValueError("addon_add exige une PlanVersion cible.")
        target = PlanVersion.objects.select_related("plan").get(pk=target_plan_version.pk)
        current_plan_version_id = None
        future_entries = list(current_entries) + [{
            "item_id": None,
            "plan_version_id": target.pk,
            "item_type": SubscriptionPlanType.ADDON,
            "at": at,
            "source_id": f"preview:{target.pk}",
        }]
    elif kind == SubscriptionTransitionKind.ADDON_REMOVE:
        if source_item is None:
            raise ValueError("addon_remove exige source_item.")
        source_item = SubscriptionItem.objects.select_related("plan_version__plan").get(pk=source_item.pk, subscription=subscription)
        target = source_item.plan_version
        current_plan_version_id = str(source_item.plan_version_id)
        future_entries = [entry for entry in current_entries if entry["item_id"] != source_item.pk]
    else:
        raise ValueError("Type de Transition inconnu.")

    _, current_values = _aggregate_versions(subscription.subject, current_entries, at=at)
    features, target_values = _aggregate_versions(subscription.subject, future_entries, at=at)

    gained = []
    lost = []
    quota_changes = []
    warnings = []
    feature_by_code = {feature.code: feature for feature in features.values()}
    for code in sorted(set(current_values) | set(target_values)):
        before = current_values.get(code)
        after = target_values.get(code)
        if not _source_value(before) and _source_value(after):
            gained.append(code)
        if _source_value(before) and not _source_value(after):
            lost.append(code)
        feature = feature_by_code.get(code)
        if feature is None or feature.value_type not in {FeatureValueType.INTEGER, FeatureValueType.DECIMAL} or before == after:
            continue
        measurement = measure_feature_usage(feature, subscription.subject)
        usage = measurement.value if measurement is not None else None
        over_limit = False
        if usage is not None and after is not None:
            over_limit = Decimal(str(usage)) > Decimal(str(after))
        quota_changes.append(
            SubscriptionQuotaChange(
                feature_code=code,
                current_value=before,
                target_value=after,
                usage=usage,
                over_limit_after_change=over_limit,
            )
        )
        if over_limit:
            warnings.append(f"over_limit_after_change:{code}")

    requirements = tuple(
        PlanRequirement.objects.filter(
            plan_version=target,
            phase=RequirementPhase.ACQUISITION,
        ).order_by("position", "key")
    ) if kind != SubscriptionTransitionKind.ADDON_REMOVE else ()
    eligibility = None
    if kind != SubscriptionTransitionKind.ADDON_REMOVE:
        eligibility = resolve_plan_eligibility(
            subscription.subject,
            target,
            self_service=request_origin == "self_service",
            at=at,
        )

    return SubscriptionChangePreview(
        kind=kind,
        current_plan_version_id=current_plan_version_id,
        target_plan_version_id=str(target.pk),
        features_gained=tuple(gained),
        features_lost=tuple(lost),
        quota_changes=tuple(quota_changes),
        requirement_keys=tuple(requirement.key for requirement in requirements),
        payment_requirement_keys=tuple(
            requirement.key for requirement in requirements if requirement.mode == RequirementMode.PAYMENT
        ),
        eligibility=eligibility,
        warnings=tuple(warnings),
    )
