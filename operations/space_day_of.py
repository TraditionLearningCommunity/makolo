from __future__ import annotations

from django.utils import timezone

from scanner.permissions import user_can_scan_activity

from .occurrence_live import resolve_occurrence_live


DAY_OF_PHASES = {"arrival", "live"}


def build_space_operator_day_of(*, occurrence, actor, observed_at=None):
    """Compose an occurrence-scoped Space operator projection from Operations owners."""
    if occurrence.activity.space_id is None:
        return None

    now = observed_at or timezone.now()
    live = resolve_occurrence_live(
        occurrence=occurrence,
        actor=actor,
        observed_at=now,
    )
    if live is None or live.get("perspective") not in {"space", "operator"}:
        return None

    phase = live.get("phase")
    if phase not in DAY_OF_PHASES:
        return None

    occurrence_id = str(occurrence.pk)
    activity_id = str(occurrence.activity_id)
    space = occurrence.activity.space
    capabilities = ["open_live"]
    scanner = live.get("scanner") or {}
    can_scan = user_can_scan_activity(actor, occurrence.activity, occurrence=occurrence)
    if can_scan:
        capabilities.append("open_scanner")

    return {
        "identity": {"kind": "occurrence", "id": occurrence_id},
        "context": {
            "scope": "space",
            "perspective": live.get("perspective"),
            "space": {
                "kind": "space",
                "id": str(space.pk),
                "slug": space.slug,
                "name": space.name,
            },
            "activity": {
                "kind": "activity",
                "id": activity_id,
                "title": occurrence.activity.title,
            },
            "phase": phase,
        },
        "occurrence": live.get("occurrence") or {},
        "timing": live.get("timing") or {},
        "readiness": live.get("operational_readiness") or {},
        "capacity": live.get("capacity") or [],
        "access_control": live.get("access") or {},
        "queues": live.get("queue") or [],
        "placement": live.get("placement") or [],
        "checkpoints": live.get("checkpoints") or [],
        "incidents": {"truth": "unavailable", "items": []},
        "live": {
            "available": True,
            "phase": phase,
            "spatial": live.get("spatial") or {},
            "next_action": live.get("next_action") or {},
        },
        "scanner": scanner,
        "capabilities": capabilities,
        "links": {
            "live": f"/api/v1/operations/occurrences/{occurrence_id}/live/",
            "readiness": f"/api/v1/operations/occurrences/{occurrence_id}/readiness/",
            "queues": f"/api/v1/operations/occurrences/{occurrence_id}/queues/",
            "checkpoints": f"/api/v1/operations/occurrences/{occurrence_id}/checkpoints/",
            "placement_plans": f"/api/v1/operations/occurrences/{occurrence_id}/placement-plans/",
            **(
                {"scanner": f"/api/v1/scanner/occurrences/{occurrence_id}/context/"}
                if can_scan
                else {}
            ),
        },
    }
