from datetime import timedelta

from django.utils import timezone

from .occurrence_live import resolve_occurrence_live


OFFLINE_ACTION_PACK_SCHEMA = "operations.offline_action_pack"
OFFLINE_ACTION_PACK_SCHEMA_VERSION = 1
OFFLINE_ACTION_PACK_FRESH_FOR = timedelta(minutes=1)
OFFLINE_ACTION_PACK_EXPIRES_AFTER = timedelta(minutes=15)

_SOURCE_KEYS = {
    "access": "access.access",
    "placement": "operations.placement",
    "flow": "operations.checkpoints",
    "checkpoints": "operations.checkpoints",
    "queue": "operations.queue",
    "capacity": "capacity",
    "scanner": "scanner.assignments",
    "spatial": "m6.spatiotemporal",
    "operational_readiness": "operations.readiness",
    "next_action": "operations.occurrence_live",
}

_OFFLINE_OMITTED_KEYS = {
    "credential",
    "credentials",
    "email",
    "itinerary_url",
    "location_history",
    "payment",
    "payments",
    "phone",
    "phone_number",
    "public_id",
    "qr",
    "qr_code",
    "secret",
    "token",
    "url",
}


def offline_action_pack_freshness(*, occurrence, phase, generated_at, evaluated_at=None):
    """Return the client-visible freshness contract for a generated pack.

    The pack is a read snapshot only. Freshness controls whether the snapshot
    should still be displayed offline; it never controls server-side authority.
    """
    evaluated_at = evaluated_at or generated_at
    fresh_until = generated_at + OFFLINE_ACTION_PACK_FRESH_FOR
    expires_at = generated_at + OFFLINE_ACTION_PACK_EXPIRES_AFTER

    if occurrence.end_at is not None:
        expires_at = min(expires_at, occurrence.end_at)
        fresh_until = min(fresh_until, expires_at)

    if phase in {"after", "cancelled"}:
        fresh_until = generated_at
        expires_at = generated_at

    if evaluated_at >= expires_at:
        state = "expired"
    elif evaluated_at >= fresh_until:
        state = "stale"
    else:
        state = "fresh"

    return {
        "state": state,
        "fresh_until": fresh_until,
        "expires_at": expires_at,
        "stale": state != "fresh",
        "expired": state == "expired",
        "refresh_required": state != "fresh",
    }


def _sanitize_offline_value(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_offline_value(item)
            for key, item in value.items()
            if key.lower() not in _OFFLINE_OMITTED_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_offline_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_offline_value(item) for item in value]
    return value


def _provenance_payload(*, occurrence, live):
    sources = ["activities.occurrence"]
    for key, source in _SOURCE_KEYS.items():
        if key in live and source not in sources:
            sources.append(source)
    return {
        "projection": "operations.occurrence_live",
        "occurrence_updated_at": occurrence.updated_at,
        "sources": sources,
    }


def resolve_offline_action_pack(*, occurrence, actor, generated_at=None, evaluated_at=None):
    """Build a serializable, viewer-aware offline read snapshot.

    No authority is encoded here. Mutations must continue through canonical
    server APIs, which re-evaluate current permissions, Mandates and domain
    state at execution time.
    """
    generated_at = generated_at or timezone.now()
    live = resolve_occurrence_live(occurrence=occurrence, actor=actor, observed_at=generated_at)
    if live is None:
        return None
    snapshot = _sanitize_offline_value(live)

    return {
        "schema": OFFLINE_ACTION_PACK_SCHEMA,
        "schema_version": OFFLINE_ACTION_PACK_SCHEMA_VERSION,
        "generated_at": generated_at,
        "freshness": offline_action_pack_freshness(
            occurrence=occurrence,
            phase=live["phase"],
            generated_at=generated_at,
            evaluated_at=evaluated_at,
        ),
        "provenance": _provenance_payload(occurrence=occurrence, live=live),
        "data_policy": {
            "scope": "minimum_operational",
            "viewer_aware": True,
            "excluded_categories": [
                "credentials",
                "contact_details",
                "payment_data",
                "raw_qr",
                "secrets",
                "action_urls",
                "location_history",
            ],
        },
        "execution_contract": {
            "offline_data_grants_authority": False,
            "server_revalidation_required": True,
            "revocation_policy": "server_current_state",
            "revalidate": [
                "permissions",
                "mandates",
                "occurrence",
                "access",
                "checkpoint",
                "queue",
                "placement",
                "capacity",
            ],
        },
        "snapshot": snapshot,
    }
