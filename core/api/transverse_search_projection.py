"""Permission-first retrieval of already-known personal Journey/Access realities."""
from django.urls import reverse

from personal_assets.selectors import personal_assets_for_controller
from groups.selectors import groups_for_profile

from access.models import AccessStatus
from journeys.models import JourneyStatus


from core.participant_selectors import (
    participant_access_search,
    participant_accesses,
    participant_journey_search,
    participant_journeys,
)

LIMIT = 24
MAX_LIMIT = 50
MAX_QUERY = 120


def build_profile_search(*, profile, query, offset=0, limit=LIMIT):
    if not query:
        return {
            "actor_context": {"kind": "profile"},
            "query": "",
            "items": [],
            "page": {"count": 0, "offset": offset, "limit": limit, "has_more": False},
            "coverage": {"state": "partial", "owners": ["journey", "access", "personal_asset", "group"]},
        }
    # Both selectors are beneficiary-scoped BEFORE any free text match.
    journeys = participant_journey_search(
        participant_journeys(profile).prefetch_related(None), query
    ).order_by("-created_at", "pk")
    accesses = participant_access_search(
        participant_accesses(profile).prefetch_related(None), query
    ).order_by("-created_at", "pk")
    journey_rows = list(journeys[:offset + limit])
    access_rows = list(accesses[:offset + limit])
    entries = []
    for row in journey_rows:
        is_past = row.status in {
            JourneyStatus.FULFILLED, JourneyStatus.REJECTED,
            JourneyStatus.CANCELLED, JourneyStatus.EXPIRED,
        }
        # The owner detail remains the destination; historical classification
        # does not create another Journey or expose another person's Access.
        entries.append((
            row.created_at, "journey", str(row.pk),
            {
                "source": {"kind": "journey", "id": str(row.pk)},
                "title": row.activity.title,
                "human_type": "Démarche",
                "relation": "Ma démarche",
                "historical": is_past,
                "context": "Historique" if is_past else "En cours",
                "destination": reverse("personal-detail-projections:journey-detail", kwargs={"pk": row.pk}),
            },
        ))
    for row in access_rows:
        is_past = row.status in {
            AccessStatus.USED, AccessStatus.CANCELLED, AccessStatus.REVOKED,
            AccessStatus.EXPIRED, AccessStatus.TRANSFERRED,
        }
        entries.append((
            row.created_at, "access", str(row.pk),
            {
                "source": {"kind": "access", "id": str(row.pk)},
                "title": row.activity.title,
                "human_type": "Accès",
                "relation": "Mon accès",
                "historical": is_past,
                "context": "Historique" if is_past else "Accès",
                "destination": reverse("personal-detail-projections:access-detail", kwargs={"pk": row.pk}),
            },
        ))
    # Personal resources are owned by the document controller, never by Search.
    assets = personal_assets_for_controller(profile).filter(
        title__icontains=query
    ).order_by("-created_at", "pk")
    for row in assets[:offset + limit]:
        entries.append((
            row.created_at, "personal_asset", str(row.pk),
            {
                "source": {"kind": "personal_asset", "id": str(row.pk)},
                "title": row.title,
                "human_type": "Document",
                "relation": "Ma ressource",
                "historical": False,
                "context": "Moi",
                "destination": reverse(
                    "personal-projections:resource-detail", kwargs={"pk": row.pk}
                ),
            },
        ))
    groups = groups_for_profile(profile).filter(
        space__isnull=True,
        name__icontains=query
    ).order_by("-created_at", "pk")
    for row in groups[:offset + limit]:
        entries.append((
            row.created_at, "group", str(row.pk),
            {
                "source": {"kind": "group", "id": str(row.pk)},
                "title": row.name,
                "human_type": "Groupe",
                "relation": "Mon collectif",
                "historical": False,
                "context": "Moi",
                "destination": reverse(
                    "personal-projections:group-detail", kwargs={"pk": row.pk}
                ),
            },
        ))
    entries.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    total = journeys.count() + accesses.count() + assets.count() + groups.count()
    selected = [row[3] for row in entries[offset:offset + limit]]
    return {
        "actor_context": {"kind": "profile"},
        "query": query,
        "items": selected,
        "page": {
            "count": total, "offset": offset, "limit": limit,
            "has_more": offset + len(selected) < total,
        },
        "coverage": {"state": "partial", "owners": ["journey", "access"]},
    }
