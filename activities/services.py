from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Activity, Occurrence, OccurrencePlace, OccurrencePlaceRole, OccurrenceStatus


@transaction.atomic
def create_activity(*, space, created_by, title, **fields) -> Activity:
    if space is None:
        raise ValidationError({"space": "Toute nouvelle activité doit appartenir à un Espace."})
    activity = Activity(space=space, created_by=created_by, title=title.strip(), **fields)
    activity.full_clean()
    activity.save()
    return activity


@transaction.atomic
def update_activity_common(*, activity: Activity, **fields) -> Activity:
    allowed = {"space", "created_by", "title", "short_description", "description", "status", "visibility"}
    unexpected = set(fields) - allowed
    if unexpected:
        raise ValidationError(f"Champs Activity non pris en charge: {', '.join(sorted(unexpected))}.")
    for name, value in fields.items():
        setattr(activity, name, value)
    activity.full_clean()
    activity.save(update_fields=[*fields.keys(), "updated_at"] if fields else ["updated_at"])
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
    occurrence.start_at = start_at
    occurrence.end_at = end_at
    if timezone is not None:
        occurrence.timezone = timezone
    occurrence.full_clean()
    occurrence.save(update_fields=["start_at", "end_at", "timezone", "updated_at"])
    return occurrence


@transaction.atomic
def set_occurrence_status(*, occurrence: Occurrence, status: str) -> Occurrence:
    if status not in OccurrenceStatus.values:
        raise ValidationError({"status": "Statut d'occurrence invalide."})
    occurrence.status = status
    occurrence.full_clean()
    occurrence.save(update_fields=["status", "updated_at"])
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
