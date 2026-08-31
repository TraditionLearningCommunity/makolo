from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from requirements.contracts import RequirementAssessmentState

from .contracts import (
    CatalogVisibility,
    PlanEligibilityStatus,
    PlanVersionStatus,
    RequirementDisclosure,
    SubscriptionItemStatus,
    SubscriptionPlanType,
    SubscriptionStatus,
    SubscriptionTransitionKind,
    SubscriptionTransitionStatus,
)
from .eligibility import resolve_plan_eligibility
from .entitlements import resolve_effective_entitlements
from .models import FeatureDefinition, PlanVersion
from .ongoing_models import SubscriptionOngoingRequirementState
from .runtime_models import SubscriptionItem
from .transition_models import OPEN_TRANSITION_STATUSES, SubscriptionTransition


@dataclass(frozen=True)
class SubscriptionProductView:
    subscription: object
    subject_label: str
    can_manage: bool
    status: dict[str, Any]
    current_base: dict[str, Any] | None
    active_addons: tuple[dict[str, Any], ...]
    capabilities: tuple[dict[str, Any], ...]
    catalog: tuple[dict[str, Any], ...]
    transition: dict[str, Any] | None
    ongoing_conditions: tuple[dict[str, Any], ...]


_SUBSCRIPTION_STATUS = {
    SubscriptionStatus.ACTIVE: ("Actif", "Votre abonnement est opérationnel.", "success"),
    SubscriptionStatus.GRACE: (
        "Action requise",
        "Une condition de votre abonnement doit être régularisée avant l’échéance indiquée.",
        "warning",
    ),
    SubscriptionStatus.SUSPENDED: (
        "Capacités limitées",
        "Certaines capacités sont temporairement indisponibles. Vos données existantes sont conservées.",
        "danger",
    ),
    SubscriptionStatus.CLOSED: ("Fermé", "Cet abonnement n’est plus actif.", "neutral"),
}

_TRANSITION_STATUS = {
    SubscriptionTransitionStatus.REQUESTED: ("Demande reçue", "Votre demande a bien été enregistrée."),
    SubscriptionTransitionStatus.IN_PROGRESS: ("En cours", "Makolo vérifie les conditions nécessaires."),
    SubscriptionTransitionStatus.READY: ("Prête", "Toutes les conditions nécessaires sont remplies."),
    SubscriptionTransitionStatus.COMPLETED: ("Terminée", "Le changement de formule est terminé."),
    SubscriptionTransitionStatus.REJECTED: ("Non aboutie", "La demande ne peut pas être finalisée."),
    SubscriptionTransitionStatus.CANCELLED: ("Annulée", "La demande a été annulée."),
    SubscriptionTransitionStatus.EXPIRED: ("Expirée", "La demande a expiré avant sa finalisation."),
    SubscriptionTransitionStatus.FAILED: ("À reprendre", "Une erreur a empêché la finalisation de la demande."),
}

_ELIGIBILITY_STATUS = {
    PlanEligibilityStatus.AVAILABLE: ("Disponible", "Cette formule peut être demandée.", "success"),
    PlanEligibilityStatus.CONDITIONALLY_AVAILABLE: (
        "Conditions à remplir",
        "Cette formule peut être demandée, mais certaines conditions doivent encore être remplies.",
        "warning",
    ),
    PlanEligibilityStatus.NOT_ELIGIBLE: (
        "Non disponible",
        "Cette formule n’est pas disponible dans votre situation actuelle.",
        "neutral",
    ),
}

_ASSESSMENT_COMPLETE = {
    RequirementAssessmentState.SATISFIED,
    RequirementAssessmentState.NOT_APPLICABLE,
}


def _subject_label(subscription):
    if subscription.profile_id:
        user = subscription.profile
        return user.full_name or user.username
    return subscription.space.name


def _benefits(version):
    return tuple(
        {
            "title": benefit.title,
            "description": benefit.description,
            "icon": benefit.icon,
            "highlighted": benefit.is_highlighted,
        }
        for benefit in version.benefits.all()
    )


def _item_card(item):
    version = item.plan_version
    return {
        "item_id": str(item.pk),
        "plan_version_id": str(version.pk),
        "name": version.name,
        "description": version.short_description,
        "benefits": _benefits(version),
        "kind": item.item_type,
    }


def _capability_rows(subscription):
    results = resolve_effective_entitlements(subscription.subject)
    active = {code: result for code, result in results.items() if result.effective_value is not None}
    if not active:
        return ()
    features = {
        feature.code: feature
        for feature in FeatureDefinition.objects.filter(code__in=active).order_by("domain", "name", "code")
    }
    rows = []
    for code, feature in features.items():
        result = active[code]
        if isinstance(result.effective_value, bool):
            value_label = "Inclus" if result.effective_value else "Non inclus"
        elif feature.unit:
            value_label = f"{result.effective_value} {feature.unit}"
        else:
            value_label = str(result.effective_value)
        usage_label = None
        if result.usage is not None:
            usage_label = f"{result.usage} utilisés sur {result.effective_value}"
        rows.append(
            {
                "code": code,
                "name": feature.name,
                "description": feature.description,
                "value": result.effective_value,
                "value_label": value_label,
                "usage": result.usage,
                "remaining": result.remaining,
                "usage_label": usage_label,
                "allowed": result.allowed,
                "over_limit": result.over_limit,
                "reason_code": result.reason_code,
            }
        )
    return tuple(rows)


def _safe_requirement(requirement, state):
    disclosure = requirement.disclosure
    if disclosure == RequirementDisclosure.INTERNAL:
        return None
    if disclosure == RequirementDisclosure.GENERIC:
        return {
            "label": "Condition requise",
            "detail": "Certaines conditions doivent encore être vérifiées.",
            "state": state,
            "internal": False,
        }
    return {
        "label": requirement.title or "Condition requise",
        "detail": requirement.description or None,
        "state": state,
        "internal": False,
    }


def _eligibility_requirements(result):
    rows = []
    for requirement in result.requirements:
        if not requirement.title:
            continue
        rows.append(
            {
                "label": requirement.title,
                "detail": requirement.detail,
                "state": requirement.state,
                "internal": False,
            }
        )
    return tuple(rows)


def _catalog_rows(subscription, active_items):
    active_version_ids = {item.plan_version_id for item in active_items}
    active_addon_plan_ids = {
        item.plan_id for item in active_items if item.item_type == SubscriptionPlanType.ADDON
    }
    versions = (
        PlanVersion.objects.filter(
            status=PlanVersionStatus.PUBLISHED,
            catalog_visibility=CatalogVisibility.PUBLIC,
            plan__is_active=True,
            plan__subject_type=subscription.subject_type,
        )
        .select_related("plan")
        .prefetch_related("benefits", "requirements")
        .order_by("display_order", "plan__code", "version")
    )
    rows = []
    for version in versions:
        result = resolve_plan_eligibility(subscription.subject, version, self_service=True)
        if result.status == PlanEligibilityStatus.HIDDEN:
            continue
        if version.pk in active_version_ids:
            current = True
        elif version.plan.plan_type == SubscriptionPlanType.ADDON and version.plan_id in active_addon_plan_ids:
            continue
        else:
            current = False
        label, explanation, tone = _ELIGIBILITY_STATUS[result.status]
        rows.append(
            {
                "plan_version_id": str(version.pk),
                "name": version.name,
                "description": version.short_description,
                "benefits": _benefits(version),
                "plan_type": version.plan.plan_type,
                "current": current,
                "eligibility": result.status,
                "eligibility_label": label,
                "eligibility_explanation": explanation,
                "eligibility_tone": tone,
                "requirements": _eligibility_requirements(result),
                "transition_kind": (
                    SubscriptionTransitionKind.BASE_SWITCH
                    if version.plan.plan_type == SubscriptionPlanType.BASE
                    else SubscriptionTransitionKind.ADDON_ADD
                ),
                "can_request": result.status in {
                    PlanEligibilityStatus.AVAILABLE,
                    PlanEligibilityStatus.CONDITIONALLY_AVAILABLE,
                }
                and not current,
            }
        )
    return tuple(rows)


def _transition_row(subscription):
    transition = (
        SubscriptionTransition.objects.filter(subscription=subscription)
        .select_related("target_plan_version", "source_plan_version")
        .prefetch_related("assessments__plan_requirement")
        .order_by("-requested_at", "-id")
        .first()
    )
    if transition is None:
        return None
    assessments = list(transition.assessments.all())
    conditions = tuple(
        row
        for assessment in assessments
        if (row := _safe_requirement(assessment.plan_requirement, assessment.state)) is not None
    )
    completed = sum(1 for assessment in assessments if assessment.state in _ASSESSMENT_COMPLETE)
    label, explanation = _TRANSITION_STATUS[transition.status]
    return {
        "id": str(transition.pk),
        "status": transition.status,
        "status_label": label,
        "status_explanation": explanation,
        "target_name": transition.target_plan_version.name,
        "kind": transition.kind,
        "open": transition.status in OPEN_TRANSITION_STATUSES,
        "completed_conditions": completed,
        "total_conditions": len(assessments),
        "conditions": conditions,
        "requested_at": transition.requested_at,
        "expires_at": transition.expires_at,
    }


def _ongoing_rows(subscription):
    states = (
        SubscriptionOngoingRequirementState.objects.filter(subscription=subscription)
        .select_related("plan_requirement")
        .order_by("plan_requirement__position", "id")
    )
    rows = []
    for state in states:
        if state.state in _ASSESSMENT_COMPLETE:
            continue
        row = _safe_requirement(state.plan_requirement, state.state)
        if row is not None:
            rows.append(row)
    return tuple(rows)


def build_subscription_product_view(subscription, *, can_manage, include_catalog=True):
    active_items = list(
        SubscriptionItem.objects.filter(
            subscription=subscription,
            status=SubscriptionItemStatus.ACTIVE,
        )
        .select_related("plan", "plan_version")
        .prefetch_related("plan_version__benefits")
        .order_by("item_type", "starts_at", "id")
    )
    base_item = next(
        (item for item in active_items if item.item_type == SubscriptionPlanType.BASE),
        None,
    )
    addon_items = tuple(
        item for item in active_items if item.item_type == SubscriptionPlanType.ADDON
    )
    label, explanation, tone = _SUBSCRIPTION_STATUS[subscription.status]
    return SubscriptionProductView(
        subscription=subscription,
        subject_label=_subject_label(subscription),
        can_manage=can_manage,
        status={
            "code": subscription.status,
            "label": label,
            "explanation": explanation,
            "tone": tone,
            "grace_until": subscription.grace_until,
        },
        current_base=_item_card(base_item) if base_item else None,
        active_addons=tuple(_item_card(item) for item in addon_items),
        capabilities=_capability_rows(subscription),
        catalog=_catalog_rows(subscription, active_items) if include_catalog else (),
        transition=_transition_row(subscription),
        ongoing_conditions=_ongoing_rows(subscription),
    )
