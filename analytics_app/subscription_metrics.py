from __future__ import annotations

from django.db.models import Count, Q
from django.utils import timezone

from domain_events.contracts import DomainEventType
from requirements.contracts import RequirementAssessmentState
from subscriptions.contracts import SubscriptionItemStatus, SubscriptionPlanType
from subscriptions.ongoing_models import SubscriptionOngoingRequirementState
from subscriptions.runtime_models import EntitlementGrant, Subscription, SubscriptionItem

from .models import AnalyticsFact


def build_subscription_metrics():
    """Small operational snapshot; never evaluates subject×plan eligibility globally."""
    now = timezone.now()
    status_rows = {
        row["status"]: row["total"]
        for row in Subscription.objects.values("status").annotate(total=Count("id"))
    }
    subject_rows = {
        "profile": Subscription.objects.filter(profile__isnull=False).count(),
        "space": Subscription.objects.filter(space__isnull=False).count(),
    }
    base_distribution = tuple(
        SubscriptionItem.objects.filter(
            status=SubscriptionItemStatus.ACTIVE,
            item_type=SubscriptionPlanType.BASE,
        )
        .values("plan__code")
        .annotate(total=Count("id"))
        .order_by("plan__code")
    )
    addon_distribution = tuple(
        SubscriptionItem.objects.filter(
            status=SubscriptionItemStatus.ACTIVE,
            item_type=SubscriptionPlanType.ADDON,
        )
        .values("plan__code")
        .annotate(total=Count("id"))
        .order_by("plan__code")
    )
    active_grants = EntitlementGrant.objects.filter(revoked_at__isnull=True).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gt=now)
    ).count()
    blocking_ongoing = SubscriptionOngoingRequirementState.objects.filter(
        state__in=[RequirementAssessmentState.PENDING, RequirementAssessmentState.UNSATISFIED]
    ).count()
    transition_types = (
        DomainEventType.SUBSCRIPTION_TRANSITION_REQUESTED,
        DomainEventType.SUBSCRIPTION_TRANSITION_COMPLETED,
        DomainEventType.SUBSCRIPTION_TRANSITION_REJECTED,
        DomainEventType.SUBSCRIPTION_TRANSITION_EXPIRED,
    )
    transition_counts = {
        row["fact_type"]: row["total"]
        for row in AnalyticsFact.objects.filter(fact_type__in=transition_types)
        .values("fact_type")
        .annotate(total=Count("id"))
    }
    return {
        "subjects": subject_rows,
        "statuses": status_rows,
        "base_distribution": base_distribution,
        "addon_distribution": addon_distribution,
        "active_grants": active_grants,
        "blocking_ongoing": blocking_ongoing,
        "transitions": transition_counts,
        "eligibility_available_events": AnalyticsFact.objects.filter(
            fact_type=DomainEventType.SUBSCRIPTION_ELIGIBILITY_AVAILABLE
        ).count(),
    }
