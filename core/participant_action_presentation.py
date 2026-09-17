from readiness import ReadinessStatus


JOURNEY_HEADLINES = {
    ReadinessStatus.BLOCKED: "La suite est bloquée.",
    ReadinessStatus.ACTION_REQUIRED: "Il reste quelque chose à faire.",
    ReadinessStatus.WAITING: "Ça suit son cours.",
    ReadinessStatus.READY: "Tout est prêt.",
    ReadinessStatus.COMPLETE: "Démarche terminée.",
}

JOURNEY_SUMMARIES = {
    ReadinessStatus.BLOCKED: "Un point doit être réglé avant de continuer.",
    ReadinessStatus.ACTION_REQUIRED: "Il reste une action de votre côté pour avancer.",
    ReadinessStatus.WAITING: "Vous avez fait votre part. Rien à faire pour le moment.",
    ReadinessStatus.READY: "Vous n’avez rien d’autre à préparer pour l’instant.",
    ReadinessStatus.COMPLETE: "Cette démarche est terminée.",
}

PHASE_LABELS = {
    "before": "Avant de partir",
    "arrival": "Il est temps d’y aller",
    "live": "Ce qui compte maintenant",
    "after": "Cette activité est terminée",
    "cancelled": "Cette activité est annulée",
}


def journey_action_presentation(*, journey, readiness, live=None):
    phase = live.get("phase") if live else None
    handoff = None
    if live and phase in {"arrival", "live", "after", "cancelled"}:
        handoff = {
            "phase": phase,
            "eyebrow": PHASE_LABELS[phase],
            "label": live["next_action"]["label"],
            "cta": "Ouvrir l’action en cours" if phase in {"arrival", "live"} else "Voir l’occurrence",
        }
    elif live and phase == "before" and readiness.status == ReadinessStatus.READY:
        handoff = {
            "phase": phase,
            "eyebrow": "À venir",
            "label": live["next_action"]["label"],
            "cta": "Voir les informations pratiques",
        }

    return {
        "headline": JOURNEY_HEADLINES[readiness.status],
        "summary": JOURNEY_SUMMARIES[readiness.status],
        "status": readiness.status.value,
        "action_items": tuple(readiness.action_items),
        "blocking_items": tuple(readiness.blocking_items),
        "waiting_items": tuple(readiness.waiting_items),
        "handoff": handoff,
        "has_attention": bool(readiness.action_items or readiness.blocking_items or readiness.waiting_items),
    }


def _access_presentation(rows):
    if not rows:
        return {"state": "not_required", "label": "Aucun accès à présenter", "detail": "Vous n’avez pas d’accès distinct à présenter ici."}
    if any(row["usable"] for row in rows):
        return {"state": "ready", "label": "Votre accès est prêt", "detail": "Vous pouvez l’utiliser pour cette occurrence."}
    if any(row["status"] == "pending" for row in rows):
        return {"state": "waiting", "label": "Votre accès est en préparation", "detail": "Rien à faire de votre côté pour le moment."}
    return {"state": "unavailable", "label": "Votre accès n’est pas disponible", "detail": "Ouvrez la démarche avant de vous déplacer."}


def _placement_presentation(payload):
    rows = payload["placement"]
    checks = payload["operational_readiness"]["contributors"]
    missing = any(row["reason"] == "participant_placement_missing" for row in checks)
    if rows:
        first = rows[0]
        detail = " · ".join(value for value in [first.get("parent_unit"), first.get("unit")] if value)
        return {"state": "ready", "label": "Votre place", "detail": detail, "rows": rows}
    if missing:
        return {"state": "waiting", "label": "Place en attente", "detail": "Votre place doit encore être attribuée.", "rows": ()}
    return {"state": "not_required", "label": "Aucune place attribuée", "detail": "Aucune place précise n’est nécessaire ici.", "rows": ()}


def _queue_presentation(rows):
    if not rows:
        return {"state": "none", "label": "Pas de file en cours", "detail": "Vous n’attendez pas votre tour pour le moment.", "rows": ()}
    called = next((row for row in rows if row["status"] == "called"), None)
    if called:
        return {"state": "called", "label": "C’est votre tour", "detail": called["label"], "rows": rows}
    waiting = next((row for row in rows if row["status"] == "waiting"), None)
    if waiting:
        position = waiting.get("position")
        detail = waiting["label"]
        if position is not None:
            detail = f"{detail} · position {position}"
        return {"state": "waiting", "label": "Restez disponible", "detail": detail, "rows": rows}
    return {"state": "complete", "label": "Passage terminé", "detail": rows[0]["label"], "rows": rows}


def occurrence_live_presentation(*, payload, timing):
    phase = payload["phase"]
    flow = payload["flow"]
    next_checkpoint = flow.get("next_checkpoint")
    place = payload["spatial"].get("place")
    mobility = payload["spatial"].get("mobility") or {}
    return {
        "phase": phase,
        "phase_label": PHASE_LABELS[phase],
        "next_action": payload["next_action"],
        "timing": timing,
        "place": place,
        "mobility": mobility,
        "access": _access_presentation(payload["access"]),
        "placement": _placement_presentation(payload),
        "queue": _queue_presentation(payload["queue"]),
        "next_checkpoint": next_checkpoint,
        "hazards": tuple(payload["spatial"].get("hazards") or ()),
        "advices": tuple(payload["spatial"].get("advices") or ()),
        "is_terminal": phase in {"after", "cancelled"},
        "is_live": phase in {"arrival", "live"},
    }