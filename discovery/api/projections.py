from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime, time
from decimal import Decimal

from django.utils import timezone

from core.api.projections import ProjectionContractError


_TECHNICAL_CODE_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


def _technical_code(value: str, *, field: str) -> str:
    value = (value or "").strip()
    if not _TECHNICAL_CODE_RE.fullmatch(value):
        raise ProjectionContractError(
            f"{field} doit etre un code technique stable en minuscules."
        )
    return value


def _required_text(value, *, field: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ProjectionContractError(f"{field} est requis.")
    return value


def _iso_value(value, *, field: str):
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            raise ProjectionContractError(f"{field} doit inclure une timezone.")
        return value.isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    raise ProjectionContractError(f"{field} doit etre une date ou un instant valide.")


def _resource(kind: str, object_id) -> dict:
    return {
        "kind": _technical_code(kind, field="resource.kind"),
        "id": _required_text(object_id, field="resource.id"),
    }


def _representation(card) -> dict:
    representation = card.representation
    return {
        "kind": _technical_code(representation.kind, field="representation.kind"),
        "title": card.title,
        "summary": card.summary or "",
        "image_url": representation.image_url,
        "route_label": representation.route_label,
        "eyebrow": representation.eyebrow,
    }


def _participant_relation(participant) -> dict:
    if participant is None:
        return {"state": "unknown"}
    state = _technical_code(
        participant.participant_state or "none",
        field="personal_relation.state",
    )
    availability = _technical_code(
        participant.availability or "unknown",
        field="personal_relation.availability",
    )
    return {
        "state": state,
        "availability": availability,
        "expires_at": _iso_value(
            participant.expires_at,
            field="personal_relation.expires_at",
        ),
    }


def _saved_state(saved: bool | None) -> dict:
    if saved is None:
        return {"state": "unknown"}
    if not isinstance(saved, bool):
        raise ProjectionContractError("saved doit etre un booleen ou null.")
    return {"state": "saved" if saved else "not_saved"}


def _watch_state(state: str | None) -> dict:
    return {
        "state": _technical_code(state or "unknown", field="watch.state"),
    }


def _capabilities(values: Iterable[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        code = _technical_code(value, field="capability")
        if code in seen:
            continue
        seen.add(code)
        result.append(code)
    return result


def _links(values: Mapping[str, str | None]) -> dict[str, str]:
    result = {}
    for key, href in values.items():
        if not href:
            continue
        code = _technical_code(key, field="link")
        result[code] = str(href)
    return result


def _price(price) -> dict:
    if price is None or price.minimum is None:
        return {
            "state": "unknown",
            "minimum": None,
            "currency": None,
        }
    minimum = price.minimum
    if not isinstance(minimum, Decimal):
        minimum = Decimal(str(minimum))
    state = "free" if bool(price.is_free) else "priced"
    return {
        "state": state,
        "minimum": str(minimum),
        "currency": price.currency,
    }


def _availability(state: str, *, remaining=None) -> dict:
    return {
        "state": _technical_code(state or "unknown", field="availability.state"),
        "remaining": remaining,
    }


def _existing_relation_action(card, participant):
    if participant is None or participant.participant_state in {None, "", "none"}:
        return None
    action = card.actions.primary
    if action is None or not action.enabled or not action.code:
        return None
    return (
        _technical_code(action.code, field="personal_action.code"),
        action.url,
    )


def build_possibility_projection(
    *,
    family: str,
    candidate_key: str,
    resource: Mapping[str, str],
    occurrence: Mapping[str, str] | None,
    revision: Mapping[str, str] | None,
    representation: Mapping,
    timing: Mapping | None,
    place: Mapping | None,
    owner_display_name: str | None,
    availability: Mapping,
    price: Mapping,
    personal_relation: Mapping,
    saved: Mapping,
    watch: Mapping,
    capabilities: Iterable[str],
    links: Mapping[str, str | None],
    provenance_resources: Iterable[Mapping[str, str]],
) -> dict:
    """Compose one Z3 possibility projection from already-resolved domain facts.

    This foundation is deliberately read-only. It does not search, rank, infer
    Requirement satisfaction, authorize a different participant, or mutate the
    possibility. Family adapters feed it facts already resolved by their owner
    domains and by the existing Discovery presentation layer.
    """

    family = _technical_code(family, field="identity.family")
    candidate_key = _required_text(candidate_key, field="identity.candidate_key")
    resource_ref = _resource(resource["kind"], resource["id"])
    occurrence_ref = _resource(occurrence["kind"], occurrence["id"]) if occurrence else None
    revision_ref = _resource(revision["kind"], revision["id"]) if revision else None
    provenance = [
        _resource(item["kind"], item["id"])
        for item in provenance_resources
    ]

    return {
        "identity": {
            "family": family,
            "candidate_key": candidate_key,
            "resource": resource_ref,
            "occurrence": occurrence_ref,
            "revision": revision_ref,
        },
        "representation": dict(representation),
        "timing": dict(timing) if timing is not None else None,
        "place": dict(place) if place is not None else None,
        "owner": (
            {"display_name": owner_display_name}
            if owner_display_name
            else None
        ),
        "availability": dict(availability),
        "price": dict(price),
        "personal_relation": dict(personal_relation),
        "saved": dict(saved),
        "watch": dict(watch),
        "capabilities": _capabilities(capabilities),
        "links": _links(links),
        "provenance": {"resources": provenance},
    }


def project_occurrence_possibility(
    item,
    card,
    *,
    saved: bool | None = None,
    can_save: bool = False,
    watch_state: str | None = None,
) -> dict:
    place = None
    if item.place is not None:
        place = {
            "id": item.place.id,
            "name": item.place.name,
            "locality": item.place.locality,
            "latitude": item.place.latitude,
            "longitude": item.place.longitude,
            "distance_km": item.distance_km,
        }
    timing = {
        "kind": _technical_code(item.timing_kind, field="timing.kind"),
        "start_date": _iso_value(item.start_date, field="timing.start_date"),
        "start_time": _iso_value(item.start_time, field="timing.start_time"),
        "end_date": _iso_value(item.end_date, field="timing.end_date"),
        "end_time": _iso_value(item.end_time, field="timing.end_time"),
        "start_at": _iso_value(item.start_at, field="timing.start_at"),
        "end_at": _iso_value(item.end_at, field="timing.end_at"),
        "timezone": item.timezone,
    }
    capabilities = ["view"]
    links = {"detail": card.url}
    if can_save and saved is not None:
        capabilities.append("unsave" if saved else "save")
    relation_action = _existing_relation_action(card, item.participant)
    if relation_action is not None:
        code, href = relation_action
        capabilities.append(code)
        if href:
            links[code] = href
    return build_possibility_projection(
        family=item.candidate_family,
        candidate_key=item.candidate_key,
        resource={"kind": "activity", "id": item.activity_id},
        occurrence={"kind": "occurrence", "id": item.occurrence_id},
        revision=None,
        representation=_representation(card),
        timing=timing,
        place=place,
        owner_display_name=card.operator_name or None,
        availability=_availability(
            item.availability.state,
            remaining=item.availability.remaining,
        ),
        price=_price(item.price),
        personal_relation=_participant_relation(item.participant),
        saved=_saved_state(saved),
        watch=_watch_state(watch_state),
        capabilities=capabilities,
        links=links,
        provenance_resources=(
            {"kind": "activity", "id": item.activity_id},
            {"kind": "occurrence", "id": item.occurrence_id},
        ),
    )


def project_service_possibility(
    item: Mapping,
    card,
    *,
    saved: bool | None = None,
    watch_state: str | None = None,
) -> dict:
    participant = item.get("participant")
    capabilities = ["view"]
    links = {"detail": card.url}
    if saved is not None:
        capabilities.append("unsave" if saved else "save")
    relation_action = _existing_relation_action(card, participant)
    if relation_action is not None:
        code, href = relation_action
        capabilities.append(code)
        if href:
            links[code] = href
    return build_possibility_projection(
        family=item.get("candidate_family") or "service_activity",
        candidate_key=item["candidate_key"],
        resource={"kind": "activity", "id": item["activity_id"]},
        occurrence=None,
        revision=None,
        representation=_representation(card),
        timing=None,
        place=None,
        owner_display_name=card.operator_name or None,
        availability=_availability("unknown"),
        price={"state": "unknown", "minimum": None, "currency": None},
        personal_relation=_participant_relation(participant),
        saved=_saved_state(saved),
        watch=_watch_state(watch_state),
        capabilities=capabilities,
        links=links,
        provenance_resources=(
            {"kind": "activity", "id": item["activity_id"]},
            {"kind": "service", "id": item["service_id"]},
        ),
    )


def project_funding_possibility(
    item: Mapping,
    card,
    *,
    saved: bool | None = None,
    watch_state: str | None = None,
) -> dict:
    funding = item["funding"]
    capabilities = ["view"]
    if saved is not None:
        capabilities.append("unsave" if saved else "save")
    return build_possibility_projection(
        family="funding_activity",
        candidate_key=item["candidate_key"],
        resource={"kind": "activity", "id": item["activity_id"]},
        occurrence=None,
        revision=None,
        representation=_representation(card),
        timing=None,
        place=None,
        owner_display_name=card.operator_name or None,
        availability=_availability("available"),
        price={"state": "unknown", "minimum": None, "currency": None},
        personal_relation=_participant_relation(None),
        saved=_saved_state(saved),
        watch=_watch_state(watch_state),
        capabilities=capabilities,
        links={"detail": card.url},
        provenance_resources=(
            {"kind": "activity", "id": item["activity_id"]},
            {"kind": "funding", "id": funding.pk},
        ),
    )


def project_opportunity_possibility(
    item: Mapping,
    card,
    *,
    saved: bool | None = None,
    watch_state: str | None = None,
) -> dict:
    capabilities = ["view"]
    if saved is not None:
        capabilities.append("unsave" if saved else "save")
    return build_possibility_projection(
        family=item.get("candidate_family") or "opportunity",
        candidate_key=item["candidate_key"],
        resource={"kind": "opportunity", "id": item["opportunity_id"]},
        occurrence=None,
        revision={"kind": "opportunity_revision", "id": item["revision_id"]},
        representation=_representation(card),
        timing=None,
        place=None,
        owner_display_name=card.operator_name or None,
        availability=_availability(item["temporal_state"]),
        price={"state": "unknown", "minimum": None, "currency": None},
        personal_relation=_participant_relation(None),
        saved=_saved_state(saved),
        watch=_watch_state(watch_state),
        capabilities=capabilities,
        links={"detail": card.url},
        provenance_resources=(
            {"kind": "opportunity", "id": item["opportunity_id"]},
            {"kind": "opportunity_revision", "id": item["revision_id"]},
        ),
    )
