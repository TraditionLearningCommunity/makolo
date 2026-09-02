from __future__ import annotations

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event


SHARING_EVENT_TYPES = {
    DomainEventType.SHARE_CREATED,
    DomainEventType.SHARE_DELIVERED,
    DomainEventType.SHARE_OPENED,
    DomainEventType.SHARE_ACCEPTED,
    DomainEventType.SHARE_DECLINED,
    DomainEventType.SHARE_REVOKED,
    DomainEventType.JOURNEY_STARTED_FROM_SHARE,
    DomainEventType.CAPTURE_CREATED,
    DomainEventType.CAPTURE_ABSORBED,
    DomainEventType.CAPTURE_DISCARDED,
    DomainEventType.CAPTURE_EXPIRED,
    DomainEventType.ARTIFACT_EXPORTED,
}


def _subject_context(envelope):
    payload = {
        "share_id": str(envelope.pk),
        "subject_type": envelope.subject_type,
        "intent": envelope.intent,
    }
    activity_id = None
    space_id = None
    if envelope.subject_type == "activity":
        subject = getattr(envelope, "activity_subject", None)
        if subject is not None and subject.activity_id:
            activity_id = subject.activity_id
            space_id = subject.activity.space_id
            payload["subject_id"] = str(subject.activity_id)
            if subject.occurrence_id:
                payload["occurrence_id"] = str(subject.occurrence_id)
    elif envelope.subject_type == "opportunity":
        subject = getattr(envelope, "opportunity_subject", None)
        if subject is not None and subject.opportunity_revision_id:
            payload["subject_id"] = str(subject.opportunity_revision.opportunity_id)
            payload["subject_revision_id"] = str(subject.opportunity_revision_id)
    elif envelope.subject_type == "journey":
        subject = getattr(envelope, "journey_subject", None)
        if subject is not None and subject.source_journey_id:
            payload["subject_id"] = str(subject.source_journey_id)
            activity_id = subject.source_journey.activity_id
            space_id = subject.source_journey.activity.space_id
    return payload, space_id, activity_id


def emit_share_event(*, event_type, envelope, idempotency_suffix, recipient_id=None, resulting_journey_id=None, channel=None):
    payload, space_id, activity_id = _subject_context(envelope)
    if recipient_id:
        payload["recipient_id"] = str(recipient_id)
    if resulting_journey_id:
        payload["resulting_journey_id"] = str(resulting_journey_id)
    if channel:
        payload["channel"] = channel
    return emit_domain_event(
        event_type=event_type,
        source_type="share_envelope",
        source_id=envelope.pk,
        idempotency_key=f"sharing:{envelope.pk}:{idempotency_suffix}",
        space_id=space_id,
        activity_id=activity_id,
        payload=payload,
    )


def emit_capture_event(*, event_type, capture, idempotency_suffix, resulting_type=None, resulting_id=None):
    payload = {
        "capture_id": str(capture.pk),
        "source_kind": capture.source_kind,
    }
    if resulting_type:
        payload["resulting_type"] = resulting_type
    if resulting_id:
        payload["resulting_id"] = str(resulting_id)
    return emit_domain_event(
        event_type=event_type,
        source_type="inbound_capture",
        source_id=capture.pk,
        idempotency_key=f"sharing:capture:{capture.pk}:{idempotency_suffix}",
        payload=payload,
    )


def emit_artifact_exported(*, artifact, channel):
    return emit_domain_event(
        event_type=DomainEventType.ARTIFACT_EXPORTED,
        source_type="journey_artifact",
        source_id=artifact.pk,
        idempotency_key=f"sharing:artifact:{artifact.pk}:exported:{channel}",
        activity_id=artifact.journey.activity_id,
        space_id=artifact.journey.activity.space_id,
        payload={
            "artifact_id": str(artifact.pk),
            "journey_id": str(artifact.journey_id),
            "kind": artifact.kind,
            "channel": channel,
        },
    )
