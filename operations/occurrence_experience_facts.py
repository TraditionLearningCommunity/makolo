"""Truth-qualified, minimal Live facts derived from authorized owner projections.

Snapshot timestamps describe the read, not the real-world event. Planned
Occurrence timing is deliberately never promoted to an observation.
"""
from __future__ import annotations


def _fact(*, domain, kind, label, value, source, truth="observed", occurred_at=None):
    return {
        "domain": domain,
        "kind": kind,
        "label": label,
        "value": value,
        "truth": truth,
        "source": source,
        "occurred_at": occurred_at.isoformat() if hasattr(occurred_at, "isoformat") else occurred_at,
    }


def _spatial_truth(section):
    """Qualified spatial context; destination is not observed position."""
    source = (section or {}).get("spatial") or {}
    place = source.get("place")
    zone = source.get("zone")
    mobility = source.get("mobility") or {}
    return {
        "destination": (
            {
                "truth": "planned",
                "source": "geography",
                "name": place.get("name"),
                "address_line": place.get("address_line"),
                "locality": place.get("locality"),
            }
            if place else {"truth": "unknown", "reason": "no_planned_destination"}
        ),
        "zone": (
            {"truth": "planned", "source": "geography", "name": zone.get("name")}
            if zone else {"truth": "unknown", "reason": "no_planned_zone"}
        ),
        "current_position": {
            "truth": "unknown",
            "reason": "no_observed_position",
        },
        "mobility": {
            "truth": (
                "estimated"
                if mobility.get("recommended_departure") is not None
                else "unknown"
            ),
            "source": "spatiotemporal.mobility",
            "recommended_departure": (
                mobility["recommended_departure"].isoformat()
                if hasattr(mobility.get("recommended_departure"), "isoformat")
                else mobility.get("recommended_departure")
            ),
        },
    }


def compose_live_knowledge(*, occurrence, participant, operator, institutional, observed_at):
    """Only derive facts for sections the viewer has already been authorized to see.

    An owner may later provide stronger coverage and event deltas. This
    projection does not manufacture events, a real-time stream or an
    ESTABLISHED coverage claim.
    """
    facts = []
    planned = {
        "truth": "planned",
        "source": "activities.occurrence",
        "start_at": occurrence.start_at.isoformat() if occurrence.start_at else None,
        "end_at": occurrence.end_at.isoformat() if occurrence.end_at else None,
        "start_date": occurrence.start_date.isoformat() if getattr(occurrence, "start_date", None) else None,
        "end_date": occurrence.end_date.isoformat() if getattr(occurrence, "end_date", None) else None,
        "timing_kind": getattr(occurrence, "timing_kind", None),
        "timezone": occurrence.timezone,
    }

    if participant is not None:
        for item in participant.get("access") or []:
            facts.append(_fact(
                domain="participant", kind="access_status",
                label="État de mon accès", value=item.get("status"),
                source="access.access",
            ))
        for item in participant.get("queue") or []:
            facts.append(_fact(
                domain="participant", kind="queue_status",
                label=item.get("label") or "Ma file", value={
                    "status": item.get("status"),
                    "position": item.get("position"),
                }, source="operations.queue", occurred_at=item.get("called_at"),
            ))
        for item in participant.get("placement") or []:
            facts.append(_fact(
                domain="participant", kind="placement",
                label=item.get("plan") or "Mon placement",
                value=item.get("unit"), source="operations.placement",
            ))
        for item in (participant.get("flow") or {}).get("checkpoints") or []:
            if item.get("completed"):
                facts.append(_fact(
                    domain="participant", kind="checkpoint_completed",
                    label=item.get("label") or "Étape",
                    value=True, source="operations.checkpoint",
                ))

    if operator is not None:
        for item in operator.get("queue") or []:
            facts.append(_fact(
                domain="organizer", kind="queue_snapshot",
                label=item.get("label") or "File", value={
                    "status": item.get("status"),
                    "counts": item.get("counts"),
                }, source="operations.queue",
            ))
        for item in operator.get("capacity") or []:
            facts.append(_fact(
                domain="organizer", kind="capacity_snapshot",
                label=item.get("label") or "Capacité", value={
                    "total": item.get("total"),
                    "available": item.get("available"),
                    "committed": item.get("committed"),
                    "unlimited": item.get("unlimited"),
                }, source="capacity",
            ))
        readiness = operator.get("operational_readiness") or {}
        if readiness.get("state") and readiness.get("state") != "unknown":
            facts.append(_fact(
                domain="organizer", kind="readiness",
                label="Préparation opérationnelle",
                value=readiness["state"], source="readiness",
                occurred_at=readiness.get("observed_at"),
            ))

    for journey in institutional or []:
        facts.append(_fact(
            domain="institutional", kind="journey_status",
            label="État de la démarche du Space",
            value={"journey_id": journey["id"], "status": journey["status"]},
            source="journeys.journey",
        ))

    # These are known database snapshots, not a complete Live coverage feed.
    coverage = {
        "state": "PARTIAL" if facts else "UNAVAILABLE",
        "reason": "owner_snapshots_only" if facts else "no_observed_owner_facts",
    }
    spatial = {}
    if participant is not None:
        spatial["participant"] = _spatial_truth(participant)
    if operator is not None:
        spatial["organizer"] = _spatial_truth(operator)
    return {
        "coverage": coverage,
        "snapshot_at": observed_at.isoformat(),
        "planned_timing": planned,
        "temporal_observation": {
            "truth": "unknown",
            "reason": "no_observed_occurrence_time_event",
        },
        "spatial": spatial,
        "facts": facts,
        "transitions": {
            "state": "unavailable",
            "items": [],
            "reason": "no_owner_event_delta_projection",
        },
        "media": {
            "state": "unavailable",
            "items": [],
            "reason": "no_authorized_media_projection",
        },
    }
