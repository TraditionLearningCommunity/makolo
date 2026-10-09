from __future__ import annotations

from django.urls import reverse

from access.models import AccessStatus, CredentialStatus
from core.participant_selectors import participant_accesses


DAY_OF_LIVE_PHASES = {"arrival", "live"}


def _iso(value):
    return value.isoformat() if value is not None else None


def _date(value):
    return value.isoformat() if value is not None else None


def _time(value):
    return value.isoformat() if value is not None else None


def _active_credential(access):
    return next(
        (
            credential
            for credential in access.credentials.all()
            if credential.status == CredentialStatus.ACTIVE
        ),
        None,
    )


def _access_rows(*, profile, occurrence, live_payload):
    live_by_id = {
        str(row["id"]): row
        for row in live_payload.get("access", [])
    }
    ids = list(live_by_id)
    if not ids:
        return []

    queryset = (
        participant_accesses(profile)
        .filter(pk__in=ids, occurrence=occurrence)
        .prefetch_related(None)
        .prefetch_related("credentials")
        .order_by("created_at", "id")
    )
    by_id = {str(access.pk): access for access in queryset}
    rows = []
    for access_id in ids:
        access = by_id.get(access_id)
        live_row = live_by_id[access_id]
        if access is None:
            continue
        credential = _active_credential(access)
        credential_presentable = (
            credential is not None
            and access.status == AccessStatus.VALID
            and bool(live_row.get("usable"))
        )
        links = {
            "detail": reverse(
                "personal-detail-projections:access-detail",
                kwargs={"pk": access.pk},
            )
        }
        capabilities = ["open_access"]
        if credential_presentable:
            links["credential"] = reverse(
                "personal-projections:access-credential",
                kwargs={"pk": access.pk},
            )
            capabilities.append("present_credential")
        rows.append(
            {
                "identity": {"kind": "access", "id": str(access.pk)},
                "state": access.status,
                "usable": bool(live_row.get("usable")),
                "truth": "observed",
                "validity": {
                    "from": _iso(access.valid_from),
                    "until": _iso(access.valid_until),
                },
                "credential": {
                    "available": credential is not None,
                    "type": credential.credential_type if credential is not None else None,
                    "presentable": credential_presentable,
                },
                "capabilities": capabilities,
                "links": links,
            }
        )
    return rows


def _next_movement(live_payload):
    action = live_payload.get("next_action") or {}
    return {
        "type": action.get("type") or "none",
        "reason": action.get("reason"),
        "label": action.get("label"),
        "source": action.get("source"),
        "truth": "observed",
    }


def _representation(*, phase, next_movement, spatial, accesses):
    next_type = next_movement["type"]
    if phase == "cancelled":
        return {"kind": "cancellation", "reason": "occurrence_cancelled"}
    if next_type in {"access", "access_wait"}:
        return {"kind": "access", "reason": next_movement["reason"]}
    if phase == "arrival" and (spatial.get("destination") or spatial.get("zone")):
        return {"kind": "orientation", "reason": "arrival_orientation"}
    if phase == "before":
        if spatial.get("hazards"):
            return {"kind": "adaptation", "reason": "current_hazard"}
        return {"kind": "timing", "reason": "before_occurrence"}
    if phase == "live":
        if any(row["credential"]["presentable"] for row in accesses):
            return {"kind": "live", "reason": "occurrence_active"}
        return {"kind": "live", "reason": "occurrence_active"}
    if phase == "after":
        return {"kind": "completion", "reason": "occurrence_ended"}
    return {"kind": "occurrence", "reason": "current_context"}


def _timing_payload(*, occurrence, live_payload):
    live_timing = live_payload.get("timing") or {}
    return {
        "truth": "planned",
        "kind": occurrence.timing_kind,
        "timezone": occurrence.timezone,
        "start_at": _iso(occurrence.start_at),
        "end_at": _iso(occurrence.end_at),
        "start_date": _date(occurrence.start_date),
        "start_time": _time(occurrence.start_time),
        "end_date": _date(occurrence.end_date),
        "end_time": _time(occurrence.end_time),
        "temporal_state": live_timing.get("temporal_state"),
    }


def _spatial_payload(live_payload):
    source = live_payload.get("spatial") or {}
    place = source.get("place")
    zone = source.get("zone")
    mobility = source.get("mobility") or {}
    return {
        "current_position": {
            "state": "unknown",
            "truth": "unknown",
            "reason": "participant_position_not_observed",
        },
        "destination": (
            {
                "truth": "planned",
                "id": str(place["id"]) if place.get("id") is not None else None,
                "name": place.get("name"),
                "address_line": place.get("address_line"),
                "locality": place.get("locality"),
                "timezone": place.get("timezone"),
                "access_instructions": place.get("access_instructions"),
            }
            if place
            else None
        ),
        "zone": (
            {
                "truth": "planned",
                "id": str(zone["id"]) if zone.get("id") is not None else None,
                "name": zone.get("name"),
            }
            if zone
            else None
        ),
        "mobility": {
            "truth": (
                "estimated"
                if mobility.get("recommended_departure") is not None
                else "unknown"
            ),
            "state": mobility.get("status") or "unknown",
            "recommended_departure": _iso(mobility.get("recommended_departure")),
            "itinerary_url": mobility.get("itinerary_url") or None,
        },
        "hazards": [
            {
                "kind": row.get("kind"),
                "severity": row.get("severity"),
                "summary": row.get("summary"),
                "source": row.get("source"),
                "truth": "observed",
            }
            for row in source.get("hazards", [])
        ],
    }


def _readiness_payload(live_payload):
    source = live_payload.get("operational_readiness") or {}
    groups = {
        "ready": [],
        "actor_interventions": [],
        "waiting": [],
        "blockers": [],
    }
    for row in source.get("contributors", []):
        payload = {
            "key": row.get("key"),
            "state": row.get("state"),
            "reason": row.get("reason"),
            "summary": row.get("message"),
            "source": row.get("source"),
        }
        state = row.get("state")
        if state == "satisfied":
            groups["ready"].append(payload)
        elif state == "action_required":
            groups["actor_interventions"].append(payload)
        elif state == "waiting":
            groups["waiting"].append(payload)
        elif state == "blocking":
            groups["blockers"].append(payload)
    return {
        "state": source.get("state") or "unknown",
        **groups,
    }


def _queue_payload(occurrence, live_payload):
    rows = []
    for row in live_payload.get("queue", []):
        rows.append(
            {
                "id": str(row["id"]),
                "queue_id": str(row["queue_id"]),
                "label": row.get("label"),
                "checkpoint_id": (
                    str(row["checkpoint_id"])
                    if row.get("checkpoint_id") is not None
                    else None
                ),
                "state": row.get("status"),
                "position": row.get("position"),
                "called_at": _iso(row.get("called_at")),
                "truth": "observed",
                "links": {
                    "collection": (
                        f"/api/v1/operations/occurrences/{occurrence.pk}/queues/me/"
                    ),
                    "entry": f"/api/v1/operations/queues/{row['queue_id']}/entries/me/",
                },
            }
        )
    return rows


def _placement_payload(occurrence, live_payload):
    return [
        {
            "plan_id": str(row["plan_id"]),
            "plan": row.get("plan"),
            "unit_id": str(row["unit_id"]),
            "unit": row.get("unit"),
            "parent_unit": row.get("parent_unit"),
            "truth": "observed",
            "links": {
                "collection": (
                    f"/api/v1/operations/occurrences/{occurrence.pk}/placements/me/"
                )
            },
        }
        for row in live_payload.get("placement", [])
    ]


def _checkpoint_payload(occurrence, live_payload):
    flow = live_payload.get("flow") or {}
    rows = [
        {
            "id": str(row["id"]),
            "key": row.get("key"),
            "label": row.get("label"),
            "required": bool(row.get("required")),
            "state": row.get("status"),
            "completed": bool(row.get("completed")),
            "truth": "observed",
        }
        for row in flow.get("checkpoints", [])
    ]
    next_row = flow.get("next_checkpoint")
    return {
        "items": rows,
        "next": (
            {
                "id": str(next_row["id"]),
                "label": next_row.get("label"),
                "state": next_row.get("status"),
                "blocked_reason": next_row.get("blocked_reason"),
                "truth": "observed",
            }
            if next_row
            else None
        ),
        "links": {
            "collection": (
                f"/api/v1/operations/occurrences/{occurrence.pk}/checkpoints/me/"
            )
        },
    }


def _completion_payload(occurrence, phase):
    if phase != "after":
        return None
    return {
        "state": "occurrence_ended",
        "summary": "Cette occurrence est terminée.",
        "links": {
            "history": reverse("personal-projections:history"),
            "occurrence": f"/api/v1/occurrences/{occurrence.pk}/",
        },
    }


def build_personal_day_of_data(*, profile, occurrence, live_payload):
    phase = live_payload["phase"]
    spatial = _spatial_payload(live_payload)
    accesses = _access_rows(
        profile=profile,
        occurrence=occurrence,
        live_payload=live_payload,
    )
    next_movement = _next_movement(live_payload)
    representation = _representation(
        phase=phase,
        next_movement=next_movement,
        spatial=spatial,
        accesses=accesses,
    )

    capabilities = ["open_occurrence"]
    links = {
        "self": reverse(
            "personal-projections:day-of",
            kwargs={"pk": occurrence.pk},
        ),
        "occurrence": f"/api/v1/occurrences/{occurrence.pk}/",
        "activity": f"/api/v1/activities/{occurrence.activity_id}/",
        "operational_readiness": (
            f"/api/v1/operations/occurrences/{occurrence.pk}/readiness/"
        ),
    }
    if phase in DAY_OF_LIVE_PHASES:
        links["live"] = f"/api/v1/operations/occurrences/{occurrence.pk}/live/"
        capabilities.append("open_live")
    if any(row["credential"]["presentable"] for row in accesses):
        capabilities.append("present_credential")

    return {
        "identity": {
            "kind": "occurrence_day_of",
            "occurrence_id": str(occurrence.pk),
        },
        "activity": {
            "kind": "activity",
            "id": str(occurrence.activity_id),
            "title": occurrence.activity.title,
        },
        "occurrence": {
            "kind": "occurrence",
            "id": str(occurrence.pk),
            "label": occurrence.label or None,
            "state": occurrence.status,
        },
        "situation": {
            "temporal_relation": phase,
            "occurrence_state": occurrence.status,
            "current_position": spatial["current_position"],
            "next": next_movement,
            "representation": representation,
        },
        "timing": _timing_payload(
            occurrence=occurrence,
            live_payload=live_payload,
        ),
        "spatial": spatial,
        "access": accesses,
        "queue": _queue_payload(occurrence, live_payload),
        "placement": _placement_payload(occurrence, live_payload),
        "checkpoints": _checkpoint_payload(occurrence, live_payload),
        "readiness": _readiness_payload(live_payload),
        "completion": _completion_payload(occurrence, phase),
        "capabilities": capabilities,
        "links": links,
    }
