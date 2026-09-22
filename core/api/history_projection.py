from __future__ import annotations

from django.urls import reverse

from core.history_presentation import history_access_label, history_journey_label
from core.participant_selectors import (
    participant_access_search,
    participant_journey_search,
    participant_unified_history_accesses,
    participant_unified_history_journeys,
)
from core.product_language import vocabulary_for


HISTORY_FILTER_ALL = "all"
HISTORY_FILTER_ACCESSES = "accesses"
HISTORY_FILTER_JOURNEYS = "journeys"
HISTORY_FILTERS = {
    HISTORY_FILTER_ALL,
    HISTORY_FILTER_ACCESSES,
    HISTORY_FILTER_JOURNEYS,
}
HISTORY_DEFAULT_LIMIT = 24
HISTORY_MAX_LIMIT = 50
HISTORY_SEARCH_MAX_LENGTH = 120


def _iso(value):
    return value.isoformat() if value is not None else None


def _occurrence_ref(occurrence):
    if occurrence is None:
        return None
    return {
        "kind": "occurrence",
        "id": str(occurrence.pk),
    }


def _access_item(access):
    workflow = access.journey.workflow if access.journey_id else None
    vocabulary = vocabulary_for(activity=access.activity, workflow=workflow)
    return {
        "kind": "access",
        "source": {"kind": "access", "id": str(access.pk)},
        "title": access.activity.title,
        "occurred_at": _iso(getattr(access, "history_at", access.updated_at)),
        "outcome": {
            "code": access.status,
            "label": history_access_label(access),
        },
        "representation": {
            "vertical": vocabulary.vertical,
            "label": vocabulary.access_noun,
        },
        "activity": {
            "kind": "activity",
            "id": str(access.activity_id),
            "title": access.activity.title,
        },
        "occurrence": _occurrence_ref(access.occurrence),
        "capabilities": [],
        "links": {},
    }


def _journey_item(journey):
    vocabulary = vocabulary_for(activity=journey.activity, workflow=journey.workflow)
    return {
        "kind": "journey",
        "source": {"kind": "journey", "id": str(journey.pk)},
        "title": journey.activity.title,
        "occurred_at": _iso(getattr(journey, "history_at", journey.updated_at)),
        "outcome": {
            "code": journey.status,
            "label": history_journey_label(journey),
        },
        "representation": {
            "vertical": vocabulary.vertical,
            "label": vocabulary.journey_noun,
        },
        "activity": {
            "kind": "activity",
            "id": str(journey.activity_id),
            "title": journey.activity.title,
        },
        "occurrence": _occurrence_ref(journey.occurrence),
        "capabilities": [],
        "links": {},
    }


def _projection_relations(queryset):
    return queryset.select_related(
        "activity__transport_service",
        "activity__service_details",
        "activity__funding_details",
    )


def _candidate(*, kind_rank, row, payload):
    history_at = getattr(row, "history_at", row.updated_at)
    created_at = row.created_at
    return (
        -history_at.timestamp(),
        -created_at.timestamp(),
        kind_rank,
        str(row.pk),
        payload,
    )


def build_personal_history_data(
    profile,
    *,
    observed_at,
    history_filter=HISTORY_FILTER_ALL,
    query="",
    limit=HISTORY_DEFAULT_LIMIT,
    offset=0,
):
    query = (query or "").strip()
    if history_filter not in HISTORY_FILTERS:
        raise ValueError("Filtre Historique inconnu.")

    access_qs = participant_access_search(
        participant_unified_history_accesses(profile, at=observed_at),
        query,
    )
    access_qs = _projection_relations(access_qs)

    journey_qs = participant_journey_search(
        participant_unified_history_journeys(profile),
        query,
    )
    journey_qs = _projection_relations(journey_qs)

    include_accesses = history_filter in {HISTORY_FILTER_ALL, HISTORY_FILTER_ACCESSES}
    include_journeys = history_filter in {HISTORY_FILTER_ALL, HISTORY_FILTER_JOURNEYS}
    access_count = access_qs.count() if include_accesses else 0
    journey_count = journey_qs.count() if include_journeys else 0

    window_end = offset + limit
    candidates = []
    if include_accesses:
        for row in access_qs[:window_end]:
            candidates.append(
                _candidate(kind_rank=0, row=row, payload=_access_item(row))
            )
    if include_journeys:
        for row in journey_qs[:window_end]:
            candidates.append(
                _candidate(kind_rank=1, row=row, payload=_journey_item(row))
            )

    candidates.sort(key=lambda candidate: candidate[:4])
    items = [candidate[4] for candidate in candidates[offset:window_end]]
    total = access_count + journey_count
    base = reverse("personal-projections:history")

    return {
        "filter": history_filter,
        "query": query or None,
        "items": items,
        "page": {
            "count": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(items) < total,
        },
        "links": {
            "self": base,
            "current_accesses": reverse("personal-projections:accesses"),
        },
    }
