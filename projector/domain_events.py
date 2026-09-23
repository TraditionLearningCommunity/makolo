from __future__ import annotations

from domain_events.contracts import DomainEventType

from .contracts import ProjectionChangeSignal


PROJECTOR_OCCURRENCE_EVENT_TYPES = frozenset(
    {
        DomainEventType.OCCURRENCE_CREATED,
        DomainEventType.OCCURRENCE_STATUS_CHANGED,
        DomainEventType.OCCURRENCE_RESCHEDULED,
        DomainEventType.OCCURRENCE_CANCELLED,
        DomainEventType.OCCURRENCE_REOPENED,
    }
)


def change_signal_from_domain_event(event) -> ProjectionChangeSignal | None:
    """Translate only the durable signal; reload current owner facts afterwards."""
    if event.event_type not in PROJECTOR_OCCURRENCE_EVENT_TYPES:
        return None
    if event.source_type != "occurrence" or not event.source_id:
        return None
    return ProjectionChangeSignal(
        change_ref=str(event.pk),
        fact_kind="occurrence",
        fact_id=str(event.source_id),
        event_type=event.event_type,
    )
