"""A bounded, permission-first slice of Space's owner-backed past.

Only completed Occurrences with a defensible owner time are admitted here.
Other owners are deliberately not represented as absent from the Space's past.
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

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
    # end_at describes the scheduled end of a completed owner Occurrence,
    # not a fabricated timestamp for each access, payment or technical update.
    queryset = (
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
        queryset = queryset.filter(
            Q(activity__title__icontains=query)
            | Q(label__icontains=query)
        )
    queryset = queryset.order_by("-end_at", "pk")
    count = queryset.count()
    rows = list(queryset[offset:offset + limit])
    items = [
        {
            "kind": "occurrence",
            "source": {"kind": "occurrence", "id": str(row.pk)},
            "title": row.label or row.activity.title,
            "context": {"activity": row.activity.title},
            "occurred_at": row.end_at.isoformat(),
            "time_basis": "scheduled_end_of_completed_occurrence",
            "outcome": {
                "code": row.status,
                "label": (
                    "Départ passé" if space.archetype == "transport_operator"
                    else "Session passée" if space.archetype == "education"
                    else "Séance passée"
                ),
            },
            "links": {"detail": f"/api/v1/occurrences/{row.pk}/"},
            "capabilities": ["view_detail"],
        }
        for row in rows
    ]
    return {
        "actor_context": {"kind": "space", "id": str(space.pk), "name": space.name},
        "responsibility": responsibility_key or "all",
        "query": query or None,
        "items": items,
        "page": {
            "count": count, "offset": offset, "limit": limit,
            "has_more": offset + len(items) < count,
        },
        "coverage": {
            "state": "partial",
            "owners": ["occurrence"],
            "message": (
                "Séances terminées datées et visibles dans ce contexte. "
                "Ce résultat ne représente pas toute l'histoire de l'Espace."
            ),
        },
    }
