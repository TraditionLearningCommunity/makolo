"""Space retrieval constrained by the existing Work owner's permitted scope."""
import logging

from django.db.models import Q
from django.db.utils import DatabaseError

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from organizations.space_product import operating_preset_for_space
from authorization.constants import PermissionCode
from authorization.selectors import activity_ids_with_direct_permission

from .space_history_projection import visible_history_activity_ids
from .space_relationships_projection import build_space_relationships_projection
from .space_work_projection import _activity_scope_from_responsibility
from .space_work_projection import _space_has_activity_portfolio_access

logger = logging.getLogger(__name__)

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
            "coverage": {"state": "partial", "owners": ["activity", "occurrence", "visible_space_relationships"]},
        }
    preset = operating_preset_for_space(space)
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
                "human_type": preset.primary_business_label,
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
                "human_type": (
                    "Départ" if space.archetype == "transport_operator"
                    else "Session" if space.archetype == "education"
                    else "Séance"
                ),
                "relation": row.activity.title,
                "historical": row.status in {
                    OccurrenceStatus.COMPLETED, OccurrenceStatus.CANCELLED,
                },
                "destination": f"/api/v1/occurrences/{row.pk}/",
            },
        ))
    # The relationship owner is already query- and permission-scoped.
    # Never traverse its records under an activity-only perspective.
    relation_items = []
    relations_partial = False
    unavailable_sources = []
    if _activity_scope_from_responsibility(
        profile, space, responsibility_key
    ) is None:
        try:
            relations = build_space_relationships_projection(
                profile=profile, space=space, query=query
            )
        except (DatabaseError, TimeoutError):
            # Do not interpret a failed owner as zero visible relationships.
            logger.exception("Space relationship Search source is unavailable")
            relations = None
            unavailable_sources.append("visible_space_relationships")
        relation_search = relations.get("search") if relations else None
        if relation_search:
            relation_items = relation_search["items"]
            relations_partial = relation_search["has_more"]
            for row in relation_items:
                profile_ref = row.get("profile") or {}
                owner_ref = row["owner"]
                relation = row["relation_type"]
                identity = (owner_ref, row["kind"], row["id"], relation)
                # Distinct relations to the same person are deliberately preserved.
                destination = (
                    row.get("links", {}).get("owner_web")
                    or row.get("links", {}).get("owner_api")
                )
                candidates.append((
                    None, row["kind"], ":".join(identity),
                    {
                        "source": {"kind": row["kind"], "id": row["id"]},
                        "title": row["identity"],
                        "human_type": relation,
                        "relation": relation,
                        "owner": owner_ref,
                        "historical": False,
                        "destination": destination,
                    },
                ))
    # Dated owner results ahead of undated relationships; not a global score.
    candidates.sort(
        key=lambda entry: (
            entry[0] is not None,
            entry[0].timestamp() if entry[0] else 0,
            entry[1],
            entry[2],
        ),
        reverse=True,
    )
    total = activities.count() + occurrences.count() + len(relation_items)
    result = [entry[3] for entry in candidates[offset:offset + limit]]
    return {
        "actor_context": {"kind": "space", "id": str(space.pk), "name": space.name},
        "query": query,
        "items": result,
        "page": {
            "count": total, "count_state": (
                "lower_bound" if relations_partial or unavailable_sources else "exact"
            ),
            "offset": offset, "limit": limit,
            "has_more": offset + len(result) < total,
        },
        "coverage": {
            "state": "partial",
            "owners": ["activity", "occurrence", "visible_space_relationships"],
            "limited_sources": ["visible_space_relationships"] if relations_partial else [],
            "unavailable_sources": unavailable_sources,
        },
    }
