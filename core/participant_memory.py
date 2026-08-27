from dataclasses import dataclass

from django.utils import timezone

from access.models import AccessStatus
from journeys.models import JourneyStatus

from .participant_presentation import occurrence_timing, vocabulary_for
from .participant_selectors import (
    participant_access_search,
    participant_journey_search,
    participant_unified_history_accesses,
    participant_unified_history_journeys,
)


@dataclass(frozen=True)
class ParticipantHistoryPage:
    items: list
    number: int
    has_previous: bool
    has_next: bool
    previous_page_number: int | None
    next_page_number: int | None


def _primary_place(occurrence):
    if occurrence is None:
        return None
    links = list(occurrence.place_links.all())
    primary = next((link for link in links if link.role == "primary"), None)
    return (primary or (links[0] if links else None)).place if links else None


def _access_history_label(access, *, at):
    if access.status == AccessStatus.USED:
        return "Accès utilisé"
    if access.status == AccessStatus.EXPIRED:
        return "Expiré"
    if access.status == AccessStatus.REVOKED:
        return "Révoqué"
    if access.status == AccessStatus.CANCELLED:
        return "Annulé"
    if access.status == AccessStatus.TRANSFERRED:
        return "Transféré"
    if access.status == AccessStatus.VALID and access.valid_until and access.valid_until <= at:
        return "Expiré"
    if access.status == AccessStatus.VALID and access.occurrence and access.occurrence.end_at < at:
        return "Engagement passé"
    return access.get_status_display()


def _journey_history_label(journey):
    return {
        JourneyStatus.FULFILLED: "Démarche terminée",
        JourneyStatus.REJECTED: "Demande refusée",
        JourneyStatus.CANCELLED: "Démarche annulée",
        JourneyStatus.EXPIRED: "Démarche expirée",
    }.get(journey.status, journey.get_status_display())


def _access_item(access, *, at):
    history_at = getattr(access, "history_at", None) or access.updated_at
    return {
        "kind": "access",
        "activity": access.activity,
        "occurrence": access.occurrence,
        "access": access,
        "journey": access.journey,
        "history_at": history_at,
        "status_label": _access_history_label(access, at=at),
        "vocabulary": vocabulary_for(
            activity=access.activity,
            workflow=getattr(access.journey, "workflow", None),
        ),
        "timing": occurrence_timing(access.occurrence),
        "place": _primary_place(access.occurrence),
        "operator_name": access.activity.operator_display_name,
    }


def _journey_item(journey):
    return {
        "kind": "journey",
        "activity": journey.activity,
        "occurrence": journey.occurrence,
        "access": None,
        "journey": journey,
        "history_at": journey.updated_at,
        "status_label": _journey_history_label(journey),
        "vocabulary": vocabulary_for(activity=journey.activity, workflow=journey.workflow),
        "timing": occurrence_timing(journey.occurrence),
        "place": _primary_place(journey.occurrence),
        "operator_name": journey.activity.operator_display_name,
    }


def _page_number(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 1
    return max(number, 1)


def participant_history_page(
    profile,
    *,
    q="",
    kind="all",
    page=1,
    page_size=24,
    at=None,
):
    """Merge the two canonical history sources without materializing a History table.

    Each source is filtered and ordered in the database first. Only enough rows to
    resolve the requested combined page (plus one sentinel) are loaded into Python.
    Accesses are the primary representation whenever they point to a Journey; the
    corresponding Journey is therefore excluded by the Journey selector.
    """
    at = at or timezone.now()
    number = _page_number(page)
    kind = kind if kind in {"all", "accesses", "journeys"} else "all"
    required = number * page_size + 1

    access_rows = []
    journey_rows = []
    if kind in {"all", "accesses"}:
        access_qs = participant_access_search(
            participant_unified_history_accesses(profile, at=at),
            q,
        )
        access_rows = list(access_qs[:required])
    if kind in {"all", "journeys"}:
        journey_qs = participant_journey_search(
            participant_unified_history_journeys(profile),
            q,
        )
        journey_rows = list(journey_qs[:required])

    items = [_access_item(row, at=at) for row in access_rows]
    items.extend(_journey_item(row) for row in journey_rows)
    items.sort(key=lambda item: (item["history_at"], str(item.get("access") or item.get("journey"))), reverse=True)

    start = (number - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    has_next = len(items) > end
    has_previous = number > 1
    return ParticipantHistoryPage(
        items=page_items,
        number=number,
        has_previous=has_previous,
        has_next=has_next,
        previous_page_number=number - 1 if has_previous else None,
        next_page_number=number + 1 if has_next else None,
    )


def participant_recent_history(profile, *, limit=5, at=None):
    return participant_history_page(
        profile,
        page=1,
        page_size=limit,
        at=at,
    ).items
