from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from domain_events.contracts import DomainEventType


@dataclass(frozen=True, slots=True)
class SignalContract:
    fields: dict[str, str]


NUMBER = "number"
STRING = "string"
BOOLEAN = "boolean"
IDENTIFIER = "identifier"

COMMON_FIELDS = {
    "count": NUMBER,
    "space_id": IDENTIFIER,
    "activity_id": IDENTIFIER,
}


def _contract(extra=None):
    fields = dict(COMMON_FIELDS)
    fields.update(extra or {})
    return SignalContract(fields=fields)


SIGNAL_CONTRACTS: dict[str, SignalContract] = {
    DomainEventType.PAYMENT_SUCCEEDED: _contract({
        "payment_id": IDENTIFIER,
        "commerce_order_id": IDENTIFIER,
        "journey_id": IDENTIFIER,
        "occurrence_id": IDENTIFIER,
        "payment_mode": STRING,
        "amount": NUMBER,
        "currency": STRING,
        "status": STRING,
    }),
    DomainEventType.PAYMENT_REFUNDED: _contract({
        "payment_id": IDENTIFIER,
        "commerce_order_id": IDENTIFIER,
        "journey_id": IDENTIFIER,
        "occurrence_id": IDENTIFIER,
        "payment_mode": STRING,
        "amount": NUMBER,
        "currency": STRING,
        "status": STRING,
    }),
    DomainEventType.ACCESS_USED: _contract({
        "access_id": IDENTIFIER,
        "occurrence_id": IDENTIFIER,
        "journey_id": IDENTIFIER,
        "access_use_id": IDENTIFIER,
        "previous_status": STRING,
        "status": STRING,
    }),
    DomainEventType.JOURNEY_FULFILLED: _contract({
        "journey_id": IDENTIFIER,
        "occurrence_id": IDENTIFIER,
        "workflow": STRING,
        "previous_status": STRING,
        "status": STRING,
    }),
    DomainEventType.OPPORTUNITY_REVISION_PUBLISHED: _contract({
        "opportunity_id": IDENTIFIER,
        "revision_id": IDENTIFIER,
        "version": NUMBER,
    }),
    DomainEventType.JOURNEY_STARTED_FROM_SHARE: _contract({
        "share_id": IDENTIFIER,
        "subject_type": STRING,
        "subject_id": IDENTIFIER,
        "subject_revision_id": IDENTIFIER,
        "occurrence_id": IDENTIFIER,
        "resulting_journey_id": IDENTIFIER,
        "channel": STRING,
        "intent": STRING,
    }),
    DomainEventType.CHECKPOINT_CLOSED: _contract({
        "checkpoint_id": IDENTIFIER,
        "occurrence_id": IDENTIFIER,
        "journey_id": IDENTIFIER,
        "previous_status": STRING,
        "status": STRING,
    }),
    DomainEventType.QUEUE_SERVED: _contract({
        "queue_entry_id": IDENTIFIER,
        "occurrence_id": IDENTIFIER,
        "access_id": IDENTIFIER,
        "previous_status": STRING,
        "status": STRING,
    }),
}


def contract_for(signal_kind: str) -> SignalContract | None:
    return SIGNAL_CONTRACTS.get(str(signal_kind or ""))


def field_type(signal_kind: str, name: str) -> str | None:
    contract = contract_for(signal_kind)
    return contract.fields.get(name) if contract else None


def allowed_fields(signal_kind: str) -> frozenset[str]:
    contract = contract_for(signal_kind)
    return frozenset(contract.fields) if contract else frozenset()


def _number(value: Any):
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return str(number) if number.is_finite() else None


def _safe_value(kind: str, value: Any):
    if value is None:
        return None
    if kind == NUMBER:
        return _number(value)
    if kind == BOOLEAN:
        return value if type(value) is bool else None
    if kind in {STRING, IDENTIFIER}:
        return str(value)[:255]
    return None


def sanitize_event_values(event) -> dict[str, Any]:
    """Project a canonical Domain Event into the minimal Recognition signal contract."""
    contract = contract_for(event.event_type)
    if contract is None:
        return {}
    payload = event.payload if isinstance(event.payload, dict) else {}
    values: dict[str, Any] = {"count": "1"}
    for name, kind in contract.fields.items():
        if name == "count":
            continue
        if name == "space_id":
            raw = event.space_id
        elif name == "activity_id":
            raw = event.activity_id
        else:
            raw = payload.get(name)
        cleaned = _safe_value(kind, raw)
        if cleaned is not None:
            values[name] = cleaned
    return values


def resolve_recognition_object(event, values: dict[str, Any]) -> tuple[str, str]:
    """Resolve the object whose Makolo network utility receives the finite pool.

    The Domain Event source is evidence, not necessarily the Recognition object.
    Payments, refunds, access uses, checkpoints and queue passages should roll up
    to the Occurrence/Journey/Activity they make actionable when that context is
    explicitly present.
    """
    kind = event.event_type
    if kind in {
        DomainEventType.PAYMENT_SUCCEEDED,
        DomainEventType.PAYMENT_REFUNDED,
        DomainEventType.ACCESS_USED,
        DomainEventType.CHECKPOINT_CLOSED,
        DomainEventType.QUEUE_SERVED,
    }:
        for field, object_type in (
            ("occurrence_id", "occurrence"),
            ("journey_id", "journey"),
            ("activity_id", "activity"),
        ):
            if values.get(field):
                return object_type, str(values[field])
    if kind == DomainEventType.JOURNEY_FULFILLED:
        if values.get("journey_id"):
            return "journey", str(values["journey_id"])
    if kind == DomainEventType.OPPORTUNITY_REVISION_PUBLISHED:
        if values.get("opportunity_id"):
            return "opportunity", str(values["opportunity_id"])
    if kind == DomainEventType.JOURNEY_STARTED_FROM_SHARE:
        subject_type = str(values.get("subject_type") or "").strip()
        subject_id = values.get("subject_id")
        if subject_type in {"activity", "opportunity", "journey"} and subject_id:
            return subject_type, str(subject_id)
        if values.get("resulting_journey_id"):
            return "journey", str(values["resulting_journey_id"])
    return str(event.source_type or "unknown")[:120], str(event.source_id or event.pk)[:160]


def uses_money_field(signal_kind: str, field_names: set[str]) -> bool:
    return signal_kind in {DomainEventType.PAYMENT_SUCCEEDED, DomainEventType.PAYMENT_REFUNDED} and "amount" in field_names
