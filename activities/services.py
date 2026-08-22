from django.core.exceptions import ValidationError
from django.db import transaction

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .models import (
    Activity,
    ActivityStatus,
    Occurrence,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
)


def _occurrence_scope(occurrence):
    return getattr(occurrence.activity, "space_id", None), occurrence.activity_id


@transaction.atomic
def create_activity(*, space, created_by, title, **fields) -> Activity:
    if space is None:
        raise ValidationError({"space": "Toute nouvelle activité doit appartenir à un Espace."})
    activity = Activity(space=space, created_by=created_by, title=title.strip(), **fields)
    activity.full_clean()
    activity.save()
    if activity.status == ActivityStatus.PUBLISHED:
        emit_domain_event(
            event_type=DomainEventType.ACTIVITY_PUBLISHED,
            source_type="activity",
            source_id=activity.pk,
            idempotency_key=f"activity:{activity.pk}:published",
            space_id=activity.space_id,
            activity_id=activity.pk,
            payload={
                "activity_id": str(activity.pk),
                "space_id": str(activity.space_id),
                "status": activity.status,
            },
        )
    return activity


@transaction.atomic
def update_activity_common(*, activity: Activity, **fields) -> Activity:
    allowed = {"space", "created_by", "title", "short_description", "description", "status", "visibility"}
    unexpected = set(fields) - allowed
    if unexpected:
        raise ValidationError(f"Champs Activity non pris en charge: {', '.join(sorted(unexpected))}.")
    previous_status = activity.status
    for name, value in fields.items():
        setattr(activity, name, value)
    activity.full_clean()
    activity.save(update_fields=[*fields.keys(), "updated_at"] if fields else ["updated_at"])
    if activity.status == ActivityStatus.PUBLISHED and previous_status != ActivityStatus.PUBLISHED:
        emit_domain_event(
            event_type=DomainEventType.ACTIVITY_PUBLISHED,
            source_type="activity",
            source_id=activity.pk,
            idempotency_key=f"activity:{activity.pk}:published",
            space_id=activity.space_id,
            activity_id=activity.pk,
            payload={
                "activity_id": str(activity.pk),
                "space_id": str(activity.space_id) if activity.space_id else None,
                "previous_status": previous_status,
                "status": activity.status,
            },
        )
    return activity


@transaction.atomic
def reopen_completed_activity(*, activity: Activity) -> Activity:
    """Restore a prematurely completed Activity without replaying publication."""
    if activity.status != ActivityStatus.COMPLETED:
        raise ValidationError("Seule une activité terminée peut être réouverte.")
    previous_status = activity.status
    transition_revision = activity.updated_at.isoformat() if activity.updated_at else "unknown"
    activity.status = ActivityStatus.PUBLISHED
    activity.full_clean()
    activity.save(update_fields=["status", "updated_at"])
    emit_domain_event(
        event_type=DomainEventType.ACTIVITY_REOPENED,
        source_type="activity",
        source_id=activity.pk,
        idempotency_key=f"activity:{activity.pk}:reopened:{transition_revision}"[:255],
        space_id=activity.space_id,
        activity_id=activity.pk,
        payload={
            "activity_id": str(activity.pk),
            "space_id": str(activity.space_id) if activity.space_id else None,
            "previous_status": previous_status,
            "status": activity.status,
        },
    )
    return activity


@transaction.atomic
def create_occurrence(*, activity, start_at, timezone, end_at=None, label="", status=OccurrenceStatus.DRAFT) -> Occurrence:
    occurrence = Occurrence(
        activity=activity,
        label=label,
        start_at=start_at,
        end_at=end_at,
        timezone=timezone,
        status=status,
    )
    occurrence.full_clean()
    occurrence.save()
    return occurrence


@transaction.atomic
def reschedule_occurrence(*, occurrence: Occurrence, start_at, end_at=None, timezone=None) -> Occurrence:
    previous_start = occurrence.start_at
    previous_end = occurrence.end_at
    previous_timezone = occurrence.timezone
    target_timezone = timezone if timezone is not None else occurrence.timezone
    changed = (
        previous_start != start_at
        or previous_end != end_at
        or previous_timezone != target_timezone
    )
    occurrence.start_at = start_at
    occurrence.end_at = end_at
    if timezone is not None:
        occurrence.timezone = timezone
    occurrence.full_clean()
    occurrence.save(update_fields=["start_at", "end_at", "timezone", "updated_at"])
    if changed:
        space_id, activity_id = _occurrence_scope(occurrence)
        schedule_key = "|".join(
            [
                start_at.isoformat(),
                end_at.isoformat() if end_at else "none",
                occurrence.timezone,
            ]
        )
        emit_domain_event(
            event_type=DomainEventType.OCCURRENCE_RESCHEDULED,
            source_type="occurrence",
            source_id=occurrence.pk,
            idempotency_key=f"occurrence:{occurrence.pk}:rescheduled:{schedule_key}"[:255],
            space_id=space_id,
            activity_id=activity_id,
            payload={
                "occurrence_id": str(occurrence.pk),
                "activity_id": str(activity_id),
                "previous_start_at": previous_start.isoformat(),
                "previous_end_at": previous_end.isoformat() if previous_end else None,
                "previous_timezone": previous_timezone,
                "start_at": occurrence.start_at.isoformat(),
                "end_at": occurrence.end_at.isoformat() if occurrence.end_at else None,
                "timezone": occurrence.timezone,
            },
        )
    return occurrence


@transaction.atomic
def set_occurrence_status(*, occurrence: Occurrence, status: str) -> Occurrence:
    if status not in OccurrenceStatus.values:
        raise ValidationError({"status": "Statut d'occurrence invalide."})
    previous_status = occurrence.status
    if previous_status == status:
        return occurrence
    occurrence.status = status
    occurrence.full_clean()
    occurrence.save(update_fields=["status", "updated_at"])
    if status == OccurrenceStatus.CANCELLED:
        space_id, activity_id = _occurrence_scope(occurrence)
        emit_domain_event(
            event_type=DomainEventType.OCCURRENCE_CANCELLED,
            source_type="occurrence",
            source_id=occurrence.pk,
            idempotency_key=f"occurrence:{occurrence.pk}:cancelled",
            space_id=space_id,
            activity_id=activity_id,
            payload={
                "occurrence_id": str(occurrence.pk),
                "activity_id": str(activity_id),
                "previous_status": previous_status,
                "status": status,
            },
        )
    return occurrence


@transaction.atomic
def reopen_completed_occurrence(*, occurrence: Occurrence) -> Occurrence:
    """Restore a prematurely completed Occurrence to its scheduled state."""
    if occurrence.status != OccurrenceStatus.COMPLETED:
        raise ValidationError("Seule une date terminée peut être réouverte.")
    previous_status = occurrence.status
    transition_revision = occurrence.updated_at.isoformat() if occurrence.updated_at else "unknown"
    occurrence.status = OccurrenceStatus.SCHEDULED
    occurrence.full_clean()
    occurrence.save(update_fields=["status", "updated_at"])
    space_id, activity_id = _occurrence_scope(occurrence)
    emit_domain_event(
        event_type=DomainEventType.OCCURRENCE_REOPENED,
        source_type="occurrence",
        source_id=occurrence.pk,
        idempotency_key=f"occurrence:{occurrence.pk}:reopened:{transition_revision}"[:255],
        space_id=space_id,
        activity_id=activity_id,
        payload={
            "occurrence_id": str(occurrence.pk),
            "activity_id": str(activity_id),
            "previous_status": previous_status,
            "status": occurrence.status,
        },
    )
    return occurrence


def cancel_occurrence(*, occurrence: Occurrence) -> Occurrence:
    return set_occurrence_status(occurrence=occurrence, status=OccurrenceStatus.CANCELLED)


def complete_occurrence(*, occurrence: Occurrence) -> Occurrence:
    return set_occurrence_status(occurrence=occurrence, status=OccurrenceStatus.COMPLETED)


@transaction.atomic
def attach_occurrence_place(*, occurrence: Occurrence, place, role=OccurrencePlaceRole.OTHER, position=0) -> OccurrencePlace:
    if role not in OccurrencePlaceRole.values:
        raise ValidationError({"role": "Rôle de lieu d'occurrence invalide."})
    if role == OccurrencePlaceRole.PRIMARY:
        link = OccurrencePlace.objects.select_for_update().filter(
            occurrence=occurrence,
            role=OccurrencePlaceRole.PRIMARY,
        ).order_by().first()
        if link:
            link.place = place
            link.position = position
            link.full_clean()
            link.save(update_fields=["place", "position", "updated_at"])
            return link
    link, created = OccurrencePlace.objects.get_or_create(
        occurrence=occurrence,
        place=place,
        role=role,
        defaults={"position": position},
    )
    if not created and link.position != position:
        link.position = position
        link.save(update_fields=["position", "updated_at"])
    return link
