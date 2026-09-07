from __future__ import annotations

from django.utils import timezone

from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer

from .ingest import record_signal
from .signal_contracts import resolve_recognition_object, sanitize_event_values


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


def _append_profile(contributors, profile_id, causal_mode, weight="1"):
    if not profile_id:
        return
    contributors.append({
        "subject_type": "profile",
        "subject_id": str(profile_id),
        "causal_mode": causal_mode,
        "weight": str(weight),
    })


def _causal_contributors(event):
    """Resolve only causal subjects already explicit in canonical domain facts/models."""
    contributors = []
    if event.space_id:
        contributors.append({
            "subject_type": "space",
            "subject_id": str(event.space_id),
            "causal_mode": "operate",
            "weight": "1",
        })
    payload = event.payload if isinstance(event.payload, dict) else {}

    if event.event_type == DomainEventType.JOURNEY_FULFILLED:
        _append_profile(contributors, payload.get("beneficiary_id") or payload.get("initiated_by_id"), "deliver")
    elif event.event_type == DomainEventType.OPPORTUNITY_REVISION_PUBLISHED:
        try:
            from opportunities.models import OpportunityRevision
            created_by_id = OpportunityRevision.objects.filter(pk=event.source_id).values_list("created_by_id", flat=True).first()
        except Exception:
            created_by_id = None
        _append_profile(contributors, created_by_id, "enable")
    elif event.event_type == DomainEventType.JOURNEY_STARTED_FROM_SHARE:
        try:
            from sharing.models import ShareEnvelope
            created_by_id = ShareEnvelope.objects.filter(pk=event.source_id).values_list("created_by_id", flat=True).first()
        except Exception:
            created_by_id = None
        _append_profile(contributors, created_by_id, "amplify")

    declared = payload.get("recognition_contributors", [])
    if isinstance(declared, list):
        for item in declared:
            if not isinstance(item, dict):
                continue
            subject_type = item.get("subject_type")
            subject_id = item.get("subject_id")
            if subject_type not in {"profile", "space"} or not subject_id:
                continue
            contributors.append({
                "subject_type": subject_type,
                "subject_id": str(subject_id),
                "causal_mode": str(item.get("causal_mode", "operate"))[:20],
                "weight": str(item.get("weight", item.get("share", 1)))[:40],
            })
    return contributors


def consume_recognition_event(event):
    """Create the minimal Recognition projection of a canonical Domain Event.

    The Domain Event source remains evidence. ``object_type/object_id`` identify
    the Activity/Occurrence/Journey/Opportunity whose network utility receives
    the finite pool. ``available_at`` is when Recognition observes the fact;
    ``occurred_at`` remains the immutable domain time.
    """
    values = sanitize_event_values(event)
    if not values:
        return None
    object_type, object_id = resolve_recognition_object(event, values)
    return record_signal(
        signal_id=f"domain-event:{event.pk}",
        signal_kind=event.event_type,
        object_type=object_type,
        object_id=object_id,
        outcome_identity=event.idempotency_key,
        occurred_at=event.occurred_at,
        available_at=timezone.now(),
        values=values,
        contributors=_causal_contributors(event),
        source_ref=f"domain-event:{event.pk}",
    )


register_consumer("recognition.signals", consume_recognition_event, event_types=RECOGNITION_EVENT_TYPES)
