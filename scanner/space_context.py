from __future__ import annotations

from django.utils import timezone

from events.models import Event
from scanner.permissions import get_active_assignment, user_can_scan_activity


def build_scanner_context(*, occurrence, actor, observed_at=None):
    now = observed_at or timezone.now()
    activity = occurrence.activity
    space = activity.space

    can_scan = user_can_scan_activity(actor, activity, occurrence=occurrence)
    assignment = get_active_assignment(
        actor,
        activity=activity,
        occurrence=occurrence,
    )
    if not can_scan:
        return None

    event = Event.objects.filter(activity=activity).first()
    capabilities = ["scan"]
    links = {
        "scan": f"/api/v1/scanner/occurrences/{occurrence.pk}/control/",
    }

    return {
        "identity": {"kind": "occurrence", "id": str(occurrence.pk)},
        "space": (
            {
                "kind": "space",
                "id": str(space.pk),
                "slug": space.slug,
                "name": space.name,
            }
            if space else None
        ),
        "activity": {
            "kind": "activity",
            "id": str(activity.pk),
            "title": activity.title,
        },
        "occurrence": {
            "kind": "occurrence",
            "id": str(occurrence.pk),
            "label": occurrence.label,
            "status": occurrence.status,
        },
        "control": {
            "authority": "canonical_permission",
            "assignment": (
                {
                    "id": str(assignment.pk),
                    "label": assignment.label,
                    "checkpoint_id": (
                        str(assignment.checkpoint_id)
                        if assignment.checkpoint_id
                        else None
                    ),
                }
                if assignment is not None
                else None
            ),
            "legacy_event_adapter": event is not None,
        },
        "next_scan": {
            "state": "available",
            "reason": "canonical_access_control",
        },
        "capabilities": capabilities,
        "links": {
            **links,
            "day_of": f"/api/v1/operations/occurrences/{occurrence.pk}/experience/day-of/",
        },
    }
