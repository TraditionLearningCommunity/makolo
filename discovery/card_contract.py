from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse
from django.utils.formats import date_format

from journeys.models import WorkflowKind


@dataclass(frozen=True)
class FactPresentation:
    code: str
    label: str
    value: str
    icon: str | None = None
    priority: int = 100


@dataclass(frozen=True)
class ActionPresentation:
    code: str
    role: str
    label: str
    icon: str
    state: str
    url: str | None
    emphasis: str = "light"
    enabled: bool = True


@dataclass(frozen=True)
class ParticipantActionSet:
    save: ActionPresentation
    primary: ActionPresentation | None
    share: ActionPresentation
    secondary: tuple[ActionPresentation, ...] = ()


@dataclass(frozen=True)
class RepresentationPresentation:
    kind: str
    image_url: str | None = None
    eyebrow: str | None = None
    route_label: str | None = None


@dataclass(frozen=True)
class DiscoveryCardPresentation:
    activity_id: str
    occurrence_id: str | None
    presentation_kind: str
    vertical_label: str
    title: str
    summary: str
    operator_label: str
    operator_name: str
    representation: RepresentationPresentation
    facts: tuple[FactPresentation, ...]
    participant_state: Any
    actions: ParticipantActionSet
    url: str


def _primary_action_code(participant_state: str, workflow: str | None) -> str:
    if participant_state == "payment_pending":
        return "pay"
    if participant_state == "access_valid":
        return "access"
    if participant_state in {
        "capacity_held",
        "request_pending",
        "order_pending",
        "order_confirmed",
        "journey_pending",
    }:
        return "continue"
    return {
        WorkflowKind.PURCHASE: "buy",
        WorkflowKind.RESERVATION: "reserve",
        WorkflowKind.REGISTRATION: "register",
        WorkflowKind.ORDER_APPROVAL: "request",
        WorkflowKind.INVITATION: "request",
    }.get(workflow, "start")


def _action_icon(code: str) -> str:
    return {
        "reserve": "slot",
        "buy": "ticket",
        "register": "join",
        "request": "send",
        "start": "move",
        "pay": "credit-card",
        "continue": "path",
        "access": "pass",
        "go": "navigation",
    }.get(code, "arrow-right")


def _occurrence_facts(item) -> tuple[FactPresentation, ...]:
    facts: list[FactPresentation] = []
    local_start = item.local_start
    if local_start is not None:
        facts.append(
            FactPresentation(
                code="when",
                label="Quand",
                value=f"{date_format(local_start, 'D d M')} · {local_start.strftime('%H:%M')}",
                icon="calendar-clock",
                priority=10,
            )
        )
    if item.place is not None:
        place_value = item.place.name
        if item.place.locality and item.place.locality != item.place.name:
            place_value = f"{place_value}, {item.place.locality}"
        facts.append(FactPresentation("place", "Lieu", place_value, "map-pin", 20))
    if item.price.label:
        facts.append(FactPresentation("price", "Prix", item.price.label, "wallet-cards", 30))
    if item.availability.state == "unlimited":
        facts.append(FactPresentation("capacity", "Capacité", "Illimitée", "users", 40))
    elif item.availability.remaining is not None:
        remaining = item.availability.remaining
        value = "Complet" if remaining <= 0 else f"{remaining} place{'s' if remaining != 1 else ''} restante{'s' if remaining != 1 else ''}"
        facts.append(FactPresentation("capacity", "Capacité", value, "users", 40))
    if item.distance_km is not None:
        facts.append(FactPresentation("distance", "Distance", f"{item.distance_km:g} km", "route", 50))
    return tuple(sorted(facts, key=lambda fact: fact.priority))


def present_occurrence_card(item, *, bookmarked: bool = False) -> DiscoveryCardPresentation:
    participant = item.participant
    code = _primary_action_code(participant.participant_state, None)
    if participant.participant_state == "none":
        if item.vertical == "transport":
            code = "reserve"
        elif item.vertical == "event":
            code = "register" if item.price.is_free else "buy"
    primary = None
    if item.cta_label and item.cta_url:
        primary = ActionPresentation(
            code=code,
            role="primary",
            label=item.cta_label,
            icon=_action_icon(code),
            state="available",
            url=item.cta_url,
            emphasis="primary",
            enabled=participant.availability not in {"cancelled", "completed"},
        )
    save_label = "Enregistré" if bookmarked else "Enregistrer"
    return DiscoveryCardPresentation(
        activity_id=item.activity_id,
        occurrence_id=item.occurrence_id,
        presentation_kind=item.vertical if item.vertical in {"event", "transport"} else "generic",
        vertical_label=item.vertical_label,
        title=item.title,
        summary=item.summary,
        operator_label={"event": "Organisé par", "transport": "Opéré par"}.get(item.vertical, "Proposé par"),
        operator_name=item.space_name,
        representation=RepresentationPresentation(
            kind="image" if item.image_url else ("route" if item.vertical == "transport" else "identity"),
            image_url=item.image_url,
            eyebrow=item.eyebrow,
            route_label=item.eyebrow if item.vertical == "transport" else None,
        ),
        facts=_occurrence_facts(item),
        participant_state=participant,
        actions=ParticipantActionSet(
            save=ActionPresentation(
                code="save",
                role="save",
                label=save_label,
                icon="orbit",
                state="saved" if bookmarked else "available",
                url=reverse("discovery:activity-bookmark-toggle", args=[item.activity_id]),
                emphasis="light",
            ),
            primary=primary,
            share=ActionPresentation(
                code="share",
                role="share",
                label="Partager",
                icon="share-2",
                state="available",
                url=reverse("sharing:create-occurrence", args=[item.occurrence_id]),
                emphasis="light",
            ),
        ),
        url=item.url,
    )


def present_service_card(item: dict, *, bookmarked: bool = False) -> DiscoveryCardPresentation:
    participant = item["participant"]
    primary = None
    if item.get("cta_label") and item.get("cta_url"):
        code = _primary_action_code(participant.participant_state, None)
        primary = ActionPresentation(
            code=code,
            role="primary",
            label=item["cta_label"],
            icon=_action_icon(code),
            state="available",
            url=item["cta_url"],
            emphasis="primary",
        )
    facts = [FactPresentation("kind", "Type", item.get("service_kind") or "Accompagnement", "list-checks", 10)]
    if item.get("opportunity_title"):
        facts.append(FactPresentation("context", "Contexte", item["opportunity_title"], "target", 20))
    return DiscoveryCardPresentation(
        activity_id=item["activity_id"],
        occurrence_id=None,
        presentation_kind="service",
        vertical_label=item["vertical_label"],
        title=item["title"],
        summary=item.get("summary") or "",
        operator_label="Proposé par",
        operator_name=item.get("space_name") or "",
        representation=RepresentationPresentation(kind="service", eyebrow=item.get("service_kind")),
        facts=tuple(facts),
        participant_state=participant,
        actions=ParticipantActionSet(
            save=ActionPresentation(
                code="save",
                role="save",
                label="Enregistré" if bookmarked else "Enregistrer",
                icon="orbit",
                state="saved" if bookmarked else "available",
                url=reverse("discovery:activity-bookmark-toggle", args=[item["activity_id"]]),
            ),
            primary=primary,
            share=ActionPresentation(
                code="share",
                role="share",
                label="Partager",
                icon="share-2",
                state="available",
                url=reverse("sharing:create-activity", args=[item["activity_id"]]),
            ),
        ),
        url=item["url"],
    )
