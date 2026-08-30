from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from requirements.contracts import RequirementAssessmentState, RequirementEvaluationResult, RequirementMode
from requirements.registry import RequirementConfigurationError, RequirementRegistryError, registry

from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    PlanEligibilityStatus,
    PlanVersionStatus,
    RequirementDisclosure,
    RequirementFailurePolicy,
    RequirementPhase,
    SubscriptionItemStatus,
)
from .eligibility_models import EntitlementRequirement, PlanRequirement
from .models import PlanEntitlement, PlanVersion
from .runtime_models import SubscriptionItem
from .selectors import get_subscription_for_subject


class EligibilityConfigurationError(ValidationError):
    pass


@dataclass(frozen=True)
class RequirementProjection:
    key: str
    state: str
    reason_code: str
    title: str | None = None
    detail: str | None = None
    actual_value: Any = None
    expected_value: Any = None


@dataclass(frozen=True)
class PlanEligibilityResult:
    plan_version_id: str
    status: str
    requirements: tuple[RequirementProjection, ...]
    reason_codes: tuple[str, ...]
    evaluated_at: Any


def _evaluate_requirement(requirement, subject):
    if requirement.mode != RequirementMode.AUTOMATIC:
        return RequirementEvaluationResult(
            state=RequirementAssessmentState.PENDING,
            reason_code=f"requirement.{requirement.mode}.pending",
            retryable=True,
        )
    try:
        return registry.evaluate(requirement.evaluator_key, subject=subject, config=requirement.config)
    except (RequirementRegistryError, RequirementConfigurationError, ValueError) as exc:
        raise EligibilityConfigurationError(f"Requirement catalogue invalide: {requirement.key}: {exc}") from exc


def _projection(requirement, result):
    if requirement.disclosure == RequirementDisclosure.INTERNAL:
        return RequirementProjection(
            key=requirement.key,
            state=result.state,
            reason_code="requirement.internal",
        )
    if requirement.disclosure == RequirementDisclosure.GENERIC:
        return RequirementProjection(
            key=requirement.key,
            state=result.state,
            reason_code="requirement.condition",
            title="Condition requise",
        )
    return RequirementProjection(
        key=requirement.key,
        state=result.state,
        reason_code=result.reason_code,
        title=requirement.title,
        detail=requirement.description or None,
        actual_value=result.actual_value,
        expected_value=result.expected_value,
    )


def resolve_plan_eligibility(subject, plan_version, *, self_service=True, at=None):
    at = at or timezone.now()
    version_id = getattr(plan_version, "pk", plan_version)
    version = PlanVersion.objects.select_related("plan").get(pk=version_id)
    if version.status != PlanVersionStatus.PUBLISHED:
        raise EligibilityConfigurationError("Eligibility exige une PlanVersion publiée précise.")
    if version.catalog_visibility == CatalogVisibility.INTERNAL:
        return PlanEligibilityResult(str(version.pk), PlanEligibilityStatus.HIDDEN, (), ("catalog.internal",), at)
    if self_service and version.acquisition_mode == AcquisitionMode.STAFF_ONLY:
        return PlanEligibilityResult(str(version.pk), PlanEligibilityStatus.HIDDEN, (), ("catalog.staff_only",), at)

    requirements = list(
        PlanRequirement.objects.filter(
            plan_version=version,
            phase=RequirementPhase.ACQUISITION,
        ).order_by("position", "key")
    )
    projections = []
    reason_codes = []
    has_block = False
    has_deny = False
    for requirement in requirements:
        result = _evaluate_requirement(requirement, subject)
        projections.append(_projection(requirement, result))
        if not requirement.is_mandatory or result.state in {
            RequirementAssessmentState.SATISFIED,
            RequirementAssessmentState.NOT_APPLICABLE,
        }:
            continue
        reason_codes.append(result.reason_code)
        if requirement.failure_policy == RequirementFailurePolicy.DENY:
            has_deny = True
        elif requirement.failure_policy == RequirementFailurePolicy.BLOCK:
            has_block = True

    if has_deny:
        status = PlanEligibilityStatus.NOT_ELIGIBLE
    elif has_block:
        status = PlanEligibilityStatus.CONDITIONALLY_AVAILABLE
    else:
        status = PlanEligibilityStatus.AVAILABLE
    return PlanEligibilityResult(str(version.pk), status, tuple(projections), tuple(reason_codes), at)


def eligible_plan_versions(subject, *, include_unlisted=False, self_service=True):
    qs = PlanVersion.objects.filter(status=PlanVersionStatus.PUBLISHED).select_related("plan").prefetch_related("requirements")
    if not include_unlisted:
        qs = qs.filter(catalog_visibility=CatalogVisibility.PUBLIC)
    return tuple(resolve_plan_eligibility(subject, version, self_service=self_service) for version in qs)


def evaluate_subscription_requirements(subscription, *, phase=RequirementPhase.ONGOING, at=None):
    at = at or timezone.now()
    items = SubscriptionItem.objects.filter(
        subscription=subscription,
        status=SubscriptionItemStatus.ACTIVE,
        starts_at__lte=at,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))
    requirements = PlanRequirement.objects.filter(
        plan_version_id__in=items.values("plan_version_id"),
        phase=phase,
    ).select_related("plan_version__plan").order_by("plan_version_id", "position", "key")
    subject = subscription.profile or subscription.space
    return tuple((requirement, _evaluate_requirement(requirement, subject)) for requirement in requirements)


def entitlement_requirement_block(subject, feature_code, *, at=None):
    at = at or timezone.now()
    subscription = get_subscription_for_subject(subject)
    if subscription is None:
        return None
    active_versions = SubscriptionItem.objects.filter(
        subscription=subscription,
        status=SubscriptionItemStatus.ACTIVE,
        starts_at__lte=at,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at)).values("plan_version_id")
    entitlement_ids = PlanEntitlement.objects.filter(
        plan_version_id__in=active_versions,
        feature__code=feature_code,
    ).values("id")
    requirements = EntitlementRequirement.objects.filter(
        plan_entitlement_id__in=entitlement_ids,
        is_mandatory=True,
    ).order_by("position", "key")
    for requirement in requirements:
        result = _evaluate_requirement(requirement, subject)
        if result.state not in {RequirementAssessmentState.SATISFIED, RequirementAssessmentState.NOT_APPLICABLE}:
            return result.reason_code
    return None
