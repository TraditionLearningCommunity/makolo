from __future__ import annotations

from .contracts import RequirementDisclosure
from .eligibility_models import PlanRequirement
from .models import FeatureDefinition, PlanVersion
from .transition_preview import preview_subscription_change


def _requirement_map(target_version, keys):
    if not keys:
        return {}
    return {
        requirement.key: requirement
        for requirement in PlanRequirement.objects.filter(
            plan_version=target_version,
            key__in=keys,
        ).order_by("position", "key")
    }


def _requirement_rows(requirements, keys):
    rows = []
    for key in keys:
        requirement = requirements.get(key)
        if requirement is None or requirement.disclosure == RequirementDisclosure.INTERNAL:
            continue
        if requirement.disclosure == RequirementDisclosure.GENERIC:
            rows.append(
                {
                    "label": "Condition requise",
                    "detail": "Certaines conditions seront vérifiées après confirmation.",
                }
            )
        else:
            rows.append(
                {
                    "label": requirement.title or "Condition requise",
                    "detail": requirement.description or None,
                }
            )
    return tuple(rows)


def build_subscription_change_preview(
    *,
    subscription,
    kind,
    target_plan_version=None,
    source_item=None,
    request_origin="self_service",
):
    preview = preview_subscription_change(
        subscription=subscription,
        kind=kind,
        target_plan_version=target_plan_version,
        source_item=source_item,
        request_origin=request_origin,
    )
    target = PlanVersion.objects.select_related("plan").get(pk=preview.target_plan_version_id)
    current = (
        PlanVersion.objects.select_related("plan").filter(pk=preview.current_plan_version_id).first()
        if preview.current_plan_version_id
        else None
    )
    feature_codes = set(preview.features_gained) | set(preview.features_lost)
    feature_codes.update(change.feature_code for change in preview.quota_changes)
    features = {
        feature.code: feature
        for feature in FeatureDefinition.objects.filter(code__in=feature_codes)
    }
    requirement_keys = tuple(dict.fromkeys((*preview.requirement_keys, *preview.payment_requirement_keys)))
    requirements = _requirement_map(target, requirement_keys)

    def feature_label(code):
        feature = features.get(code)
        return feature.name if feature else "Capacité"

    quota_rows = []
    for change in preview.quota_changes:
        quota_rows.append(
            {
                "label": feature_label(change.feature_code),
                "current_value": change.current_value,
                "target_value": change.target_value,
                "usage": change.usage,
                "over_limit_after_change": change.over_limit_after_change,
            }
        )

    visible_payment_requirement = any(
        requirements.get(key) is not None
        and requirements[key].disclosure == RequirementDisclosure.VISIBLE
        for key in preview.payment_requirement_keys
    )

    return {
        "kind": preview.kind,
        "current_name": current.name if current else None,
        "target_name": target.name,
        "target_plan_version_id": str(target.pk),
        "features_gained": tuple(feature_label(code) for code in preview.features_gained),
        "features_lost": tuple(feature_label(code) for code in preview.features_lost),
        "quota_changes": tuple(quota_rows),
        "requirements": _requirement_rows(requirements, preview.requirement_keys),
        "has_payment_requirement": visible_payment_requirement,
        "eligibility": preview.eligibility.status if preview.eligibility else None,
        "warnings": tuple(
            "Votre usage actuel dépasse la future limite. Vos données existantes seront conservées, "
            "mais de nouvelles opérations pourront être bloquées jusqu’au retour sous la limite."
            for warning in preview.warnings
            if warning.startswith("over_limit_after_change:")
        ),
    }
