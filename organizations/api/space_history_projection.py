"""A bounded, permission-first slice of Space's owner-backed past.

Only completed Occurrences with a defensible owner time are admitted here.
Other owners are deliberately not represented as absent from the Space's past.
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from django.urls import reverse
from commerce.models import CommerceOrder, CommerceOrderStatus
from authorization.selectors import has_direct_space_permission

from activities.models import Occurrence, OccurrenceStatus
from authorization.constants import PermissionCode
from authorization.selectors import activity_ids_with_direct_permission

from .space_work_projection import (
    _activity_scope_from_responsibility,
    _space_has_activity_portfolio_access,
    _visible_activity_ids,
)


DEFAULT_LIMIT = 24
MAX_LIMIT = 50
MAX_QUERY_LENGTH = 120


def visible_history_activity_ids(*, profile, space, responsibility_key=None):
    """Resolve authority before any historical owner is queried."""
    ids = _visible_activity_ids(profile, space)
    lens = _activity_scope_from_responsibility(profile, space, responsibility_key)
    if lens == set():
        return None
    if lens is not None:
        ids &= lens
    if not _space_has_activity_portfolio_access(profile, space):
        owner_ids = set(
            activity_ids_with_direct_permission(profile, PermissionCode.ACTIVITY_MANAGE)
        ) | set(
            activity_ids_with_direct_permission(
                profile, PermissionCode.ACTIVITY_OPERATIONS_VIEW
            )
        )
        ids &= owner_ids
    return ids


def build_space_history_projection(
    *, profile, space, query="", responsibility_key=None,
    offset=0, limit=DEFAULT_LIMIT, observed_at=None,
):
    ids = visible_history_activity_ids(
        profile=profile, space=space, responsibility_key=responsibility_key
    )
    if ids is None:
        return None

    observed_at = observed_at or timezone.now()
    occurrences = (
        Occurrence.objects.filter(
            activity__space=space,
            activity_id__in=ids,
            status=OccurrenceStatus.COMPLETED,
            end_at__isnull=False,
            end_at__lte=observed_at,
        )
        .select_related("activity")
    )
    if query:
        occurrences = occurrences.filter(
            Q(activity__title__icontains=query)
            | Q(label__icontains=query)
            | Q(place_links__place__name__icontains=query)
            | Q(place_links__place__locality__icontains=query)
        ).distinct()
    occurrences = occurrences.order_by("-end_at", "pk")

    # Orders may be historical when their actual cancellation time exists.
    # The Space Orders owner controls authority before its rows are queried.
    orders_visible = has_direct_space_permission(
        profile, space, PermissionCode.ORDERS_VIEW
    )
    orders = CommerceOrder.objects.none()
    if orders_visible:
        orders = CommerceOrder.objects.filter(
            payee_space=space,
            journey__activity_id__in=ids,
            status=CommerceOrderStatus.CANCELLED,
            cancelled_at__isnull=False,
            cancelled_at__lte=observed_at,
        ).select_related("journey__activity")
        if query:
            orders = orders.filter(
                Q(reference__icontains=query)
                | Q(journey__activity__title__icontains=query)
            )
        orders = orders.order_by("-cancelled_at", "pk")

    window_end = offset + limit
    candidates = []
    for occurrence in occurrences[:window_end]:
        outcome = (
            "Départ passé" if space.archetype == "transport_operator"
            else "Session passée" if space.archetype == "education"
            else "Séance passée"
        )
        candidates.append((
            -occurrence.end_at.timestamp(), "occurrence", str(occurrence.pk),
            {
                "kind": "occurrence",
                "source": {"kind": "occurrence", "id": str(occurrence.pk)},
                "title": occurrence.label or occurrence.activity.title,
                "context": {"activity": occurrence.activity.title},
                "occurred_at": occurrence.end_at.isoformat(),
                "time_basis": "scheduled_end_of_completed_occurrence",
                "outcome": {"code": occurrence.status, "label": outcome},
                "links": {
                    "detail": f"/api/v1/occurrences/{occurrence.pk}/"
                },
                "capabilities": ["view_detail"],
            },
        ))
    if orders_visible:
        for order in orders[:window_end]:
            candidates.append((
                -order.cancelled_at.timestamp(), "commerce_order", str(order.pk),
                {
                    "kind": "commerce_order",
                    "source": {"kind": "commerce_order", "id": str(order.pk)},
                    "title": f"Commande {order.reference}",
                    "context": {
                        "activity": order.journey.activity.title,
                    },
                    "occurred_at": order.cancelled_at.isoformat(),
                    "time_basis": "owner_cancelled_at",
                    "outcome": {
                        "code": order.status,
                        "label": "Commande annulée",
                    },
                    "links": {
                        "detail": reverse(
                            "organizations:console-orders",
                            kwargs={"slug": space.slug},
                        )
                    },
                    "capabilities": ["view_detail"],
                },
            ))
    candidates.sort(key=lambda item: item[:3])
    items = [candidate[3] for candidate in candidates[offset:window_end]]
    total = occurrences.count() + (orders.count() if orders_visible else 0)
    owners = ["occurrence"]
    if orders_visible:
        owners.append("commerce_order")
    return {
        "actor_context": {"kind": "space", "id": str(space.pk), "name": space.name},
        "responsibility": responsibility_key or "all",
        "query": query or None,
        "items": items,
        "page": {
            "count": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(items) < total,
        },
        "coverage": {
            "state": "partial",
            "owners": owners,
            "message": (
                "Expériences terminées et annulations datées visibles. "
                "D'autres réalités passées peuvent ne pas être couvertes."
            ),
        },
    }
