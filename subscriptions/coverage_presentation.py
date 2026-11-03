"""Private read projections for funded subscriptions: no beneficiary activity or usage disclosure."""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .coverage_models import AllocationStatus, SubscriptionCoverage, SubscriptionCoverageAllocation
from .coverage_entitlements import resolved_funded_allocations


def _allocation_label(allocation):
    if allocation.group_id:
        return "group"
    if allocation.profile_id:
        return "profile"
    return "space"


def coverage_card(coverage, *, include_allocations=False):
    result = {
        "id": str(coverage.pk),
        "plan_version_id": str(coverage.plan_version_id),
        "plan_name": coverage.plan_version.name,
        "plan_type": coverage.plan_version.plan.plan_type,
        "status": coverage.status,
        "quantity": coverage.purchased_quantity,
        "starts_at": coverage.starts_at.isoformat(),
        "ends_at": coverage.ends_at.isoformat(),
        "allocated": coverage.allocations.filter(
            status=AllocationStatus.ACTIVE, group__isnull=True,
        ).count(),
    }
    if include_allocations:
        result["allocations"] = [
            {
                "id": str(assignment.pk),
                "target_type": _allocation_label(assignment),
                "target_id": str(assignment.profile_id or assignment.space_id or assignment.group_id),
                "status": assignment.status,
                "selected_base": assignment.selected_base,
                "group_parent_id": str(assignment.group_parent_id) if assignment.group_parent_id else None,
            }
            for assignment in coverage.allocations.select_related("group_parent").order_by("created_at", "id")
        ]
    return result


def payer_coverages(*, profile=None, space=None):
    if bool(profile) == bool(space):
        raise ValueError("Profil XOR Espace est requis.")
    lookup = Q(payer_profile=profile) if profile else Q(payer_space=space)
    coverages = (
        SubscriptionCoverage.objects.filter(lookup)
        .select_related("plan_version__plan")
        .order_by("-created_at", "pk")[:100]
    )
    return [coverage_card(coverage, include_allocations=True) for coverage in coverages]


def beneficiary_coverages(*, subject):
    """Only direct allocations, never exposure of financier's billing or other beneficiaries."""
    from django.contrib.auth import get_user_model
    from organizations.models import Organization
    if isinstance(subject, get_user_model()):
        target = Q(profile=subject)
    elif isinstance(subject, Organization):
        target = Q(space=subject)
    else:
        raise ValueError("Le sujet doit être un Profil ou un Espace.")
    assignments = (
        SubscriptionCoverageAllocation.objects.filter(target, group__isnull=True)
        .select_related("coverage__plan_version__plan")
        .order_by("-created_at", "id")[:100]
    )
    effective_ids = {row.pk for row in resolved_funded_allocations(subject)}
    return [
        {
            "id": str(a.pk),
            "status": a.status,
            "selected_base": a.selected_base,
            "plan_name": a.coverage.plan_version.name,
            "plan_type": a.coverage.plan_version.plan.plan_type,
            "starts_at": a.starts_at.isoformat(),
            "ends_at": a.ends_at.isoformat(),
            "effective": a.pk in effective_ids,
        }
        for a in assignments
    ]
