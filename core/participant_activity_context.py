from __future__ import annotations

from collections import defaultdict

from django.db.models import Prefetch

from access.models import Access
from commerce.models import CommerceOrder
from journeys.models import Journey
from payments.models import Payment

from .participant_selectors import ParticipantStateContext


def participant_state_context_for_activities(profile, activities):
    """Build the canonical participant presentation context for Activity-only cards.

    This is the Activity-first counterpart of participant_state_context(), used by
    verticals such as Service that do not require an Occurrence. It is read-only,
    batched and deliberately preserves the same Access/Journey/Commerce/Payment
    relations consumed by resolve_participant_activity_state().
    """

    context = ParticipantStateContext(profile=profile)
    if not bool(getattr(profile, "is_authenticated", False)):
        return context

    activity_ids = {activity.pk for activity in activities}
    if not activity_ids:
        return context

    accesses = list(
        Access.objects.filter(beneficiary=profile, activity_id__in=activity_ids)
        .select_related("activity", "occurrence", "journey")
        .order_by("-created_at", "id")
    )
    orders = CommerceOrder.objects.select_related("buyer").prefetch_related(
        Prefetch("payments", queryset=Payment.objects.order_by("-created_at", "id"))
    ).order_by("-created_at", "id")
    journeys = list(
        Journey.objects.filter(beneficiary=profile, activity_id__in=activity_ids)
        .select_related("activity", "occurrence", "beneficiary")
        .prefetch_related(
            "requests",
            "capacity_reservations__pool",
            Prefetch("commerce_orders", queryset=orders),
        )
        .order_by("-created_at", "id")
    )

    accesses_by_activity = defaultdict(list)
    for access in accesses:
        accesses_by_activity[access.activity_id].append(access)
    journeys_by_activity = defaultdict(list)
    for journey in journeys:
        journeys_by_activity[journey.activity_id].append(journey)

    context.accesses_by_activity = dict(accesses_by_activity)
    context.journeys_by_activity = dict(journeys_by_activity)
    return context
