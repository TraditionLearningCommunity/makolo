from __future__ import annotations

from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer

from .ingest import record_signal


RECOGNITION_EVENT_TYPES = frozenset({
    DomainEventType.PAYMENT_SUCCEEDED,
    DomainEventType.PAYMENT_REFUNDED,
    DomainEventType.ACCESS_USED,
    DomainEventType.JOURNEY_FULFILLED,
    DomainEventType.OPPORTUNITY_REVISION_PUBLISHED,
    DomainEventType.JOURNEY_STARTED_FROM_SHARE,
    DomainEventType.CHECKPOINT_CLOSED,
    DomainEventType.QUEUE_SERVED,
})


def consume_recognition_event(event):
    payload = dict(event.payload or {})
    values = dict(payload)
    values.setdefault("count", 1)
    if event.space_id:
        values.setdefault("space_id", str(event.space_id))
    if event.activity_id:
        values.setdefault("activity_id", str(event.activity_id))
    contributors = []
    if event.space_id:
        contributors.append({"subject_type": "space", "subject_id": str(event.space_id), "causal_mode": "operate", "weight": "1"})
    for item in payload.get("recognition_contributors", []) if isinstance(payload.get("recognition_contributors"), list) else []:
        if isinstance(item, dict):
            contributors.append(item)
    return record_signal(
        signal_id=f"domain-event:{event.pk}",
        signal_kind=event.event_type,
        object_type=event.source_type,
        object_id=event.source_id or str(event.pk),
        outcome_identity=event.idempotency_key,
        occurred_at=event.occurred_at,
        available_at=event.created_at,
        values=values,
        contributors=contributors,
        source_ref=f"domain-event:{event.pk}",
    )


register_consumer("recognition.signals", consume_recognition_event, event_types=RECOGNITION_EVENT_TYPES)
