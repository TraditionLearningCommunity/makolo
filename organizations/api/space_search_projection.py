"""Space retrieval constrained by the existing Work owner's permitted scope."""
from django.db.models import Q

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import PermissionCode
from authorization.selectors import activity_ids_with_direct_permission

from .space_history_projection import visible_history_activity_ids
from .space_work_projection import _space_has_activity_portfolio_access

LIMIT = 24
MAX_LIMIT = 50
MAX_QUERY = 120


def build_space_search(*, profile, space, query, responsibility_key=None, offset=0, limit=LIMIT):
    ids = visible_history_activity_ids(
        profile=profile, space=space, responsibility_key=responsibility_key
    )
    if ids is None:
        return None
    if not query:
        return {
            "actor_context": {"kind": "space", "id": str(space.pk), "name": space.name},
            "query": "",
            "items": [],
            "page": {"count": 0, "offset": offset, "limit": limit, "has_more": False},
            "coverage": {"state": "partial", "owners": ["activity", "occurrence"]},
        }
    activities = Activity.objects.filter(
        space=space, pk__in=ids
    ).filter(title__icontains=query).order_by("-created_at", "pk")
    occurrences = Occurrence.objects.filter(
        activity__space=space, activity_id__in=ids
    ).filter(Q(label__icontains=query) | Q(activity__title__icontains=query)).select_related(
        "activity"
    ).order_by("-created_at", "pk")
    candidates = []
    for row in activities[:offset + limit]:
        candidates.append((
            row.created_at, "activity", str(row.pk),
            {
                "source": {"kind": "activity", "id": str(row.pk)},
                "title": row.title,
                "human_type": "Activité",
                "relation": "Activité du Space",
                "historical": row.status in {
                    ActivityStatus.COMPLETED, ActivityStatus.CANCELLED,
                    ActivityStatus.ARCHIVED,
                },
                "destination": f"/api/v1/activities/{row.pk}/",
            },
        ))
    for row in occurrences[:offset + limit]:
        candidates.append((
            row.created_at, "occurrence", str(row.pk),
            {
                "source": {"kind": "occurrence", "id": str(row.pk)},
                "title": row.label or row.activity.title,
                "human_type": "Séance",
                "relation": row.activity.title,
                "historical": row.status in {
                    OccurrenceStatus.COMPLETED, OccurrenceStatus.CANCELLED,
                },
                "destination": f"/api/v1/occurrences/{row.pk}/",
            },
        ))
    candidates.sort(key=lambda entry: (entry[0], entry[1], entry[2]), reverse=True)
    total = activities.count() + occurrences.count()
    result = [entry[3] for entry in candidates[offset:offset + limit]]
    return {
        "actor_context": {"kind": "space", "id": str(space.pk), "name": space.name},
        "query": query,
        "items": result,
        "page": {"count": total, "offset": offset, "limit": limit, "has_more": offset + len(result) < total},
        "coverage": {"state": "partial", "owners": ["activity", "occurrence"]},
    }
