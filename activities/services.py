from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .models import (
    Activity,
    ActivityStatus,
    Occurrence,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceSchedule,
    OccurrenceScheduleFrequency,
    OccurrenceScheduleStatus,
    OccurrenceScheduleWeekday,
    OccurrenceStatus,
    OccurrenceTimingKind,
)


def _occurrence_scope(occurrence):
    return getattr(occurrence.activity, "space_id", None), occurrence.activity_id


def _activity_payload(activity, **extra):
    payload = {
        "activity_id": str(activity.pk),
        "space_id": str(activity.space_id) if activity.space_id else None,
        "owner_profile_id": str(activity.owner_profile_id) if activity.owner_profile_id else None,
        "status": activity.status,
    }
    payload.update(extra)
    return payload


def _occurrence_timing_payload(occurrence):
    return {
        "timing_kind": occurrence.timing_kind,
        "start_date": occurrence.start_date.isoformat() if occurrence.start_date else None,
        "start_time": occurrence.start_time.isoformat() if occurrence.start_time else None,
        "end_date": occurrence.end_date.isoformat() if occurrence.end_date else None,
        "end_time": occurrence.end_time.isoformat() if occurrence.end_time else None,
        "start_at": occurrence.start_at.isoformat() if occurrence.start_at else None,
        "end_at": occurrence.end_at.isoformat() if occurrence.end_at else None,
        "timezone": occurrence.timezone,
    }


@transaction.atomic
def create_activity(*, created_by, title, space=None, owner_profile=None, **fields) -> Activity:
    if bool(space) == bool(owner_profile):
        raise ValidationError(
            "Toute nouvelle Activity doit appartenir soit à un Profil, soit à un Espace."
        )
    if owner_profile is not None and owner_profile.pk != getattr(created_by, "pk", None):
        raise ValidationError(
            {"owner_profile": "Une Activity personnelle doit être créée par son propriétaire."}
        )

    activity = Activity(
        space=space,
        owner_profile=owner_profile,
        created_by=created_by,
        title=title.strip(),
        **fields,
    )
    activity.full_clean()
    activity.save()

    if owner_profile is not None:
        grant_activity_role(
            profile=owner_profile,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=created_by,
            source="personal-activity-ownership",
        )

    if activity.status == ActivityStatus.PUBLISHED:
        emit_domain_event(
            event_type=DomainEventType.ACTIVITY_PUBLISHED,
            source_type="activity",
            source_id=activity.pk,
            idempotency_key=f"activity:{activity.pk}:published",
            space_id=activity.space_id,
            activity_id=activity.pk,
            payload=_activity_payload(activity),
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
            payload=_activity_payload(activity, previous_status=previous_status),
        )
    return activity


@transaction.atomic
def reopen_completed_activity(*, activity: Activity) -> Activity:
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
        payload=_activity_payload(activity, previous_status=previous_status),
    )
    return activity


@transaction.atomic
def create_occurrence(
    *,
    activity,
    timezone,
    start_at=None,
    end_at=None,
    start_date=None,
    start_time=None,
    end_date=None,
    end_time=None,
    timing_kind=OccurrenceTimingKind.EXACT,
    label="",
    status=OccurrenceStatus.DRAFT,
    schedule=None,
    schedule_local_date=None,
) -> Occurrence:
    occurrence = Occurrence(
        activity=activity,
        label=label,
        start_at=start_at,
        end_at=end_at,
        start_date=start_date,
        start_time=start_time,
        end_date=end_date,
        end_time=end_time,
        timing_kind=timing_kind,
        timezone=timezone,
        status=status,
        schedule=schedule,
        schedule_local_date=schedule_local_date,
    )
    occurrence.full_clean()
    occurrence.save()
    return occurrence


@transaction.atomic
def reschedule_occurrence(
    *,
    occurrence: Occurrence,
    start_at=None,
    end_at=None,
    timezone=None,
    start_date=None,
    start_time=None,
    end_date=None,
    end_time=None,
    timing_kind=None,
) -> Occurrence:
    previous = _occurrence_timing_payload(occurrence)
    target_timezone = timezone if timezone is not None else occurrence.timezone

    if timing_kind is not None:
        occurrence.timing_kind = timing_kind
    if timezone is not None:
        occurrence.timezone = timezone

    # Legacy exact-time callers remain supported. Structured values win when
    # explicitly supplied.
    if start_date is not None or start_time is not None or timing_kind is not None:
        occurrence.start_date = start_date if start_date is not None else occurrence.start_date
        occurrence.start_time = start_time
        occurrence.end_date = end_date
        occurrence.end_time = end_time
        occurrence.start_at = None
        occurrence.end_at = None
    else:
        occurrence.start_at = start_at
        occurrence.end_at = end_at
        occurrence.start_date = None
        occurrence.start_time = None
        occurrence.end_date = None
        occurrence.end_time = None
        occurrence.timing_kind = OccurrenceTimingKind.EXACT

    occurrence.timezone = target_timezone
    occurrence.full_clean()
    current = _occurrence_timing_payload(occurrence)
    changed = previous != current
    occurrence.save(
        update_fields=[
            "start_date",
            "start_time",
            "end_date",
            "end_time",
            "timing_kind",
            "start_at",
            "end_at",
            "timezone",
            "updated_at",
        ]
    )
    if changed:
        space_id, activity_id = _occurrence_scope(occurrence)
        schedule_key = "|".join(str(current[key]) for key in (
            "timing_kind", "start_date", "start_time", "end_date", "end_time", "timezone"
        ))
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
                "previous_timing": previous,
                **current,
            },
        )
    return occurrence


@transaction.atomic
def create_occurrence_schedule(
    *,
    activity,
    created_by,
    frequency,
    starts_on,
    timezone,
    interval=1,
    ends_on=None,
    timing_kind=OccurrenceTimingKind.EXACT,
    start_time=None,
    duration_minutes=None,
    weekdays=(),
    month_day=None,
    month=None,
    label="",
    occurrence_status=OccurrenceStatus.SCHEDULED,
) -> OccurrenceSchedule:
    schedule = OccurrenceSchedule(
        activity=activity,
        created_by=created_by,
        frequency=frequency,
        starts_on=starts_on,
        ends_on=ends_on,
        timezone=timezone,
        interval=interval,
        timing_kind=timing_kind,
        start_time=start_time,
        duration_minutes=duration_minutes,
        month_day=month_day,
        month=month,
        label=label,
        occurrence_status=occurrence_status,
    )
    schedule.full_clean()
    schedule.save()
    weekday_values = sorted(set(int(day) for day in weekdays))
    if frequency == OccurrenceScheduleFrequency.WEEKLY and not weekday_values:
        raise ValidationError({"weekdays": "Une récurrence hebdomadaire exige au moins un jour."})
    for weekday in weekday_values:
        OccurrenceScheduleWeekday.objects.create(schedule=schedule, weekday=weekday)
    return schedule


def _schedule_matches_date(schedule, day, weekday_values):
    if day < schedule.starts_on or (schedule.ends_on and day > schedule.ends_on):
        return False
    delta_days = (day - schedule.starts_on).days
    if schedule.frequency == OccurrenceScheduleFrequency.DAILY:
        return delta_days % schedule.interval == 0
    if schedule.frequency == OccurrenceScheduleFrequency.WEEKLY:
        return (delta_days // 7) % schedule.interval == 0 and day.weekday() in weekday_values
    if schedule.frequency == OccurrenceScheduleFrequency.MONTHLY:
        month_delta = (day.year - schedule.starts_on.year) * 12 + day.month - schedule.starts_on.month
        return month_delta >= 0 and month_delta % schedule.interval == 0 and day.day == schedule.month_day
    if schedule.frequency == OccurrenceScheduleFrequency.YEARLY:
        return (
            day.year >= schedule.starts_on.year
            and (day.year - schedule.starts_on.year) % schedule.interval == 0
            and day.month == schedule.month
            and day.day == schedule.month_day
        )
    return False


def _schedule_end_parts(schedule, day):
    if schedule.timing_kind != OccurrenceTimingKind.EXACT or not schedule.duration_minutes:
        return None, None
    start = datetime.combine(day, schedule.start_time, tzinfo=ZoneInfo(schedule.timezone))
    end = start + timedelta(minutes=schedule.duration_minutes)
    return end.date(), end.timetz().replace(tzinfo=None)


@transaction.atomic
def materialize_occurrence_schedule(*, schedule: OccurrenceSchedule, through_date):
    schedule = (
        OccurrenceSchedule.objects.select_for_update()
        .prefetch_related("weekdays")
        .get(pk=schedule.pk)
    )
    if schedule.status != OccurrenceScheduleStatus.ACTIVE:
        return []
    last_day = min(through_date, schedule.ends_on) if schedule.ends_on else through_date
    if last_day < schedule.starts_on:
        return []
    weekday_values = {row.weekday for row in schedule.weekdays.all()}
    created = []
    day = schedule.starts_on
    while day <= last_day:
        if _schedule_matches_date(schedule, day, weekday_values):
            end_date, end_time = _schedule_end_parts(schedule, day)
            defaults = {
                "activity": schedule.activity,
                "label": schedule.label,
                "start_date": day,
                "start_time": schedule.start_time,
                "end_date": end_date,
                "end_time": end_time,
                "timing_kind": schedule.timing_kind,
                "timezone": schedule.timezone,
                "status": schedule.occurrence_status,
            }
            try:
                occurrence, was_created = Occurrence.objects.get_or_create(
                    schedule=schedule,
                    schedule_local_date=day,
                    defaults=defaults,
                )
            except IntegrityError:
                occurrence = Occurrence.objects.get(schedule=schedule, schedule_local_date=day)
                was_created = False
            if was_created:
                created.append(occurrence)
        day += timedelta(days=1)
    return created


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
