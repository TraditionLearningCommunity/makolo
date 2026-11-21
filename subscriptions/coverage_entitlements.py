from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .contracts import SubscriptionPlanType
from .coverage_models import AllocationStatus, CoverageStatus, SubscriptionCoverageAllocation
from .coverage_services import _group_member_allowed
from .eligibility import _evaluate_requirement
from .eligibility_models import EntitlementRequirement, PlanRequirement
from .models import PlanEntitlement
from requirements.contracts import RequirementAssessmentState


_OK = {RequirementAssessmentState.SATISFIED, RequirementAssessmentState.NOT_APPLICABLE}


def _funded_version_allowed(subject, version, *, at):
    """Evaluate ongoing and per-feature conditions on the funded source itself."""
    for requirement in PlanRequirement.objects.filter(
        plan_version=version, phase="ongoing", is_mandatory=True,
    ):
        try:
            result = _evaluate_requirement(requirement, subject)
        except Exception:
            return False
        if result.state not in _OK:
            return False
    return True


def resolved_funded_allocations(subject, *, at=None):
    """Active, beneficiary-consented allocations only; a Group is never the rights subject."""
    at = at or timezone.now()
    from django.contrib.auth import get_user_model
    from organizations.models import Organization

    if isinstance(subject, get_user_model()):
        target = Q(profile=subject)
    elif isinstance(subject, Organization):
        target = Q(space=subject)
    else:
        return ()
    qs = (
        SubscriptionCoverageAllocation.objects.filter(
            target, status=AllocationStatus.ACTIVE,
            group__isnull=True, coverage__status=CoverageStatus.ACTIVE,
            starts_at__lte=at, ends_at__gt=at,
            coverage__starts_at__lte=at, coverage__ends_at__gt=at,
        )
        .select_related(
            "coverage__plan_version__plan",
            "group_parent__group", "group_parent__group_snapshot",
        )
        .order_by("-selected_at", "id")
    )
    accepted = []
    for allocation in qs:
        if allocation.group_parent_id and not _group_member_allowed(
            allocation.group_parent, allocation.profile
        ):
            continue
        if not _funded_version_allowed(subject, allocation.coverage.plan_version, at=at):
            continue
        accepted.append(allocation)
    return tuple(accepted)


def funded_feature_contributions(subject, features, allocations):
    """Return source-linked feature contributions without materializing independent grants."""
    from .entitlements import EntitlementSource

    versions = {allocation.coverage.plan_version_id for allocation in allocations}
    entitlements = (
        PlanEntitlement.objects.filter(
            plan_version_id__in=versions,
            feature__code__in=features,
            feature__is_active=True,
        )
        .select_related("feature")
    )
    requirements_by_entitlement = {}
    reqs = EntitlementRequirement.objects.filter(
        plan_entitlement__in=entitlements, is_mandatory=True,
    )
    for requirement in reqs:
        requirements_by_entitlement.setdefault(requirement.plan_entitlement_id, []).append(requirement)
    contributions = {code: [] for code in features}
    for entitlement in entitlements:
        for allocation in allocations:
            if allocation.coverage.plan_version_id != entitlement.plan_version_id:
                continue
            # A broken or unavailable evaluator must fail closed for this
            # financed source, without granting access or hiding other sources.
            eligible = True
            for requirement in requirements_by_entitlement.get(entitlement.pk, ()):
                try:
                    if _evaluate_requirement(requirement, subject).state not in _OK:
                        eligible = False
                        break
                except Exception:
                    eligible = False
                    break
            if not eligible:
                continue
            version = allocation.coverage.plan_version
            is_base = version.plan.plan_type == SubscriptionPlanType.BASE
            if is_base and not allocation.selected_base:
                continue
            source_type = "funded_base" if is_base else "funded_addon"
            contributions[entitlement.feature.code].append({
                "priority": 1 if is_base else 2,
                "at": allocation.accepted_at or allocation.starts_at,
                "source": EntitlementSource(
                    source_type=source_type,
                    source_id=str(allocation.pk),
                    value=entitlement.value,
                    plan_code=version.plan.code,
                    plan_version=version.version,
                ),
            })
    return contributions
