from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from activities.models import (
    ActivityStatus,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
    OccurrenceTimingKind,
)
from activities.services import (
    attach_occurrence_place,
    complete_occurrence,
    create_activity,
    create_occurrence,
    create_occurrence_schedule,
    materialize_occurrence_schedule,
    reopen_completed_activity,
    reopen_completed_occurrence,
    reschedule_occurrence,
    set_occurrence_status,
    update_activity_common,
)
from authorization.constants import PermissionCode
from authorization.services import can
from capacity.models import CapacityPool
from commerce.models import OfferStatus
from commerce.services import update_offer

from .models import Event, EventStatus, VenueKind
from .permissions import user_can_manage_event


UNSET = object()
CORE_ACTIVITY_FIELDS = {"title", "short_description", "description", "visibility"}
CORE_OCCURRENCE_FIELDS = {
    "start_at",
    "end_at",
    "start_date",
    "start_time",
    "end_date",
    "end_time",
    "timing_kind",
    "timezone",
}
EVENT_FIELDS = {
    "category",
    "venue",
    "cover_image",
    "registration_start_at",
    "registration_end_at",
    "metadata",
}
COMPLETED_EVENT_LOCKED_FIELDS = {
    "venue",
    *CORE_OCCURRENCE_FIELDS,
    "registration_start_at",
    "registration_end_at",
    "capacity",
}


def _ensure_can_manage(actor, event: Event) -> None:
    if not user_can_manage_event(actor, event):
        raise PermissionDenied("Vous ne pouvez pas gérer cet événement.")


def _ensure_can_create(actor, space=None) -> None:
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")
    if space is not None and not can(actor, PermissionCode.SPACE_ACTIVITIES_MANAGE, space):
        raise PermissionDenied("Vous ne pouvez pas créer d’événement dans cet Espace.")


def _event_occurrences(event, *, for_update=False):
    queryset = event.activity.occurrences.all()
    if for_update:
        queryset = queryset.select_for_update()
    return queryset.order_by("start_date", "start_time", "id")


def _occurrence_is_past(occurrence, *, now=None):
    now = now or timezone.now()
    if occurrence.end_at:
        return occurrence.end_at <= now
    if occurrence.start_at:
        return occurrence.start_at <= now
    if occurrence.start_date:
        local_today = now.astimezone(ZoneInfo(occurrence.timezone)).date()
        return (occurrence.end_date or occurrence.start_date) < local_today
    return False


def _set_occurrence_place(*, event, occurrence, venue=UNSET):
    target_venue = event.venue if venue is UNSET else venue
    if target_venue and target_venue.kind in {VenueKind.PHYSICAL, VenueKind.HYBRID}:
        if not target_venue.place_id:
            raise ValidationError({"venue": "Le lieu physique doit référencer un Place canonique."})
        return attach_occurrence_place(
            occurrence=occurrence,
            place=target_venue.place,
            role=OccurrencePlaceRole.PRIMARY,
            position=0,
        )
    OccurrencePlace.objects.filter(occurrence=occurrence, role=OccurrencePlaceRole.PRIMARY).delete()
    return None


def _capacity_source_key(event, occurrence):
    return f"event:{event.pk}:occurrence:{occurrence.pk}:capacity"


def _set_event_capacity(*, event, occurrence, total_quantity):
    """Event vocabulary routed to one Occurrence-scoped canonical CapacityPool."""
    source_key = _capacity_source_key(event, occurrence)
    pool = CapacityPool.objects.select_for_update().filter(source_key=source_key).first()
    if pool is None:
        if total_quantity is None:
            return None
        pool = CapacityPool(
            activity=event.activity,
            occurrence=occurrence,
            label="Capacité événement",
            total_quantity=total_quantity,
            source_key=source_key,
        )
        pool.save()
        return pool
    pool.activity = event.activity
    pool.occurrence = occurrence
    pool.total_quantity = total_quantity
    pool.is_active = True
    pool.save(update_fields=["activity", "occurrence", "total_quantity", "is_active", "updated_at"])
    return pool


def _clamp_offer_windows(event):
    for offer in event.activity.offers.select_for_update().all():
        values = {}
        if event.registration_start_at and (offer.available_from is None or offer.available_from < event.registration_start_at):
            values["available_from"] = event.registration_start_at
        if event.registration_end_at and (offer.available_until is None or offer.available_until > event.registration_end_at):
            values["available_until"] = event.registration_end_at
        if values:
            update_offer(offer=offer, **values)


def _event_specific_values(fields):
    return {name: fields[name] for name in EVENT_FIELDS if name in fields}


@transaction.atomic
def add_event_occurrence(
    *,
    event: Event,
    actor,
    start_at=None,
    end_at=None,
    start_date=None,
    start_time=None,
    end_date=None,
    end_time=None,
    timing_kind=OccurrenceTimingKind.EXACT,
    timezone_name="Africa/Lubumbashi",
    label="",
    venue=UNSET,
    capacity=UNSET,
):
    _ensure_can_manage(actor, event)
    if event.status in {EventStatus.CANCELLED, EventStatus.ARCHIVED, EventStatus.COMPLETED}:
        raise ValidationError("Ajoutez une date seulement à un événement brouillon ou publié.")
    occurrence = create_occurrence(
        activity=event.activity,
        start_at=start_at,
        end_at=end_at,
        start_date=start_date,
        start_time=start_time,
        end_date=end_date,
        end_time=end_time,
        timing_kind=timing_kind,
        timezone=timezone_name,
        label=label,
        status=OccurrenceStatus.SCHEDULED if event.status == EventStatus.PUBLISHED else OccurrenceStatus.DRAFT,
    )
    _set_occurrence_place(event=event, occurrence=occurrence, venue=venue)
    if capacity is not UNSET:
        _set_event_capacity(event=event, occurrence=occurrence, total_quantity=capacity)
    return occurrence


@transaction.atomic
def create_event(
    *,
    actor,
    title,
    start_at=None,
    end_at=None,
    start_date=None,
    start_time=None,
    end_date=None,
    end_time=None,
    timing_kind=OccurrenceTimingKind.EXACT,
    occurrences=None,
    organization=None,
    timezone="Africa/Lubumbashi",
    short_description="",
    description="",
    visibility="public",
    category=None,
    venue=None,
    cover_image=None,
    registration_start_at=None,
    registration_end_at=None,
    metadata=None,
    capacity=UNSET,
) -> Event:
    """Create one durable Event/Activity with zero, one or many Occurrences."""
    _ensure_can_create(actor, organization)
    activity = create_activity(
        space=organization,
        owner_profile=actor if organization is None else None,
        created_by=actor,
        title=title,
        short_description=short_description,
        description=description,
        visibility=visibility,
        status=ActivityStatus.DRAFT,
    )
    event = Event(
        activity=activity,
        category=category,
        venue=venue,
        cover_image=cover_image,
        registration_start_at=registration_start_at,
        registration_end_at=registration_end_at,
        metadata=metadata or {},
    )
    event.full_clean()
    event.save()

    specs = list(occurrences or [])
    if not specs and (start_at is not None or start_date is not None):
        specs = [
            {
                "start_at": start_at,
                "end_at": end_at,
                "start_date": start_date,
                "start_time": start_time,
                "end_date": end_date,
                "end_time": end_time,
                "timing_kind": timing_kind,
                "timezone_name": timezone,
                "capacity": capacity,
                "venue": venue,
            }
        ]
    elif capacity is not UNSET and not specs:
        raise ValidationError({"capacity": "Une capacité Event doit cibler une date précise."})

    for spec in specs:
        values = dict(spec)
        values.setdefault("timezone_name", timezone)
        values.setdefault("timing_kind", OccurrenceTimingKind.EXACT)
        if "capacity" not in values and capacity is not UNSET and len(specs) == 1:
            values["capacity"] = capacity
        add_event_occurrence(event=event, actor=actor, **values)
    return event


@transaction.atomic
def create_event_schedule(
    *,
    event: Event,
    actor,
    frequency,
    starts_on,
    timezone_name,
    materialize_through,
    interval=1,
    ends_on=None,
    timing_kind=OccurrenceTimingKind.EXACT,
    start_time=None,
    duration_minutes=None,
    weekdays=(),
    month_day=None,
    month=None,
    label="",
    venue=UNSET,
    capacity=UNSET,
):
    """Create a calendar rule; Event only orchestrates vertical defaults."""
    _ensure_can_manage(actor, event)
    if event.status in {EventStatus.CANCELLED, EventStatus.ARCHIVED, EventStatus.COMPLETED}:
        raise ValidationError("Un événement fermé ne peut pas recevoir une nouvelle récurrence.")
    schedule = create_occurrence_schedule(
        activity=event.activity,
        created_by=actor,
        frequency=frequency,
        starts_on=starts_on,
        ends_on=ends_on,
        timezone=timezone_name,
        interval=interval,
        timing_kind=timing_kind,
        start_time=start_time,
        duration_minutes=duration_minutes,
        weekdays=weekdays,
        month_day=month_day,
        month=month,
        label=label,
        occurrence_status=OccurrenceStatus.SCHEDULED if event.status == EventStatus.PUBLISHED else OccurrenceStatus.DRAFT,
    )
    created = materialize_occurrence_schedule(schedule=schedule, through_date=materialize_through)
    for occurrence in created:
        _set_occurrence_place(event=event, occurrence=occurrence, venue=venue)
        if capacity is not UNSET:
            _set_event_capacity(event=event, occurrence=occurrence, total_quantity=capacity)
    return schedule, created


@transaction.atomic
def update_event_occurrence(*, event: Event, occurrence, actor, venue=UNSET, capacity=UNSET, **timing_fields):
    _ensure_can_manage(actor, event)
    if occurrence.activity_id != event.activity_id:
        raise ValidationError("Cette date n’appartient pas à cet événement.")
    if event.status == EventStatus.COMPLETED:
        raise ValidationError("Les dates d’un événement terminé restent verrouillées.")
    if timing_fields:
        reschedule_occurrence(occurrence=occurrence, **timing_fields)
    if venue is not UNSET:
        _set_occurrence_place(event=event, occurrence=occurrence, venue=venue)
    if capacity is not UNSET:
        _set_event_capacity(event=event, occurrence=occurrence, total_quantity=capacity)
    return occurrence


@transaction.atomic
def update_event(*, event: Event, actor, organization=None, occurrence=None, **fields) -> Event:
    _ensure_can_manage(actor, event)
    activity = event.activity

    if event.status == EventStatus.COMPLETED:
        locked = COMPLETED_EVENT_LOCKED_FIELDS & fields.keys()
        if locked:
            raise ValidationError(
                "La date, le lieu, les inscriptions et la capacité d’un événement terminé restent verrouillés. "
                "Réouvrez l’événement seulement si sa clôture était une erreur."
            )
        if organization is not None and organization.pk != activity.space_id:
            raise ValidationError("Un événement terminé ne peut pas être déplacé vers un autre Espace.")

    activity_values = {name: fields[name] for name in CORE_ACTIVITY_FIELDS if name in fields}
    if organization is not None and organization.pk != activity.space_id:
        if activity.owner_profile_id:
            raise ValidationError("Le transfert d’une Activity personnelle vers un Espace n’est pas réalisé depuis ce formulaire.")
        if not can(actor, PermissionCode.SPACE_ACTIVITIES_MANAGE, organization):
            raise PermissionDenied("Vous ne pouvez pas déplacer cet événement vers cet Espace.")
        activity_values["space"] = organization
    if activity_values:
        update_activity_common(activity=activity, **activity_values)

    occurrence_fields = {name: fields[name] for name in CORE_OCCURRENCE_FIELDS if name in fields}
    if occurrence_fields:
        if occurrence is None:
            rows = list(_event_occurrences(event, for_update=True)[:2])
            if len(rows) != 1:
                raise ValidationError("Choisissez explicitement la date à modifier pour un événement multi-date.")
            occurrence = rows[0]
        update_event_occurrence(event=event, occurrence=occurrence, actor=actor, **occurrence_fields)

    event_values = _event_specific_values(fields)
    if "cover_image" in event_values and not event_values["cover_image"]:
        event_values.pop("cover_image")
    for name, value in event_values.items():
        setattr(event, name, value)
    event.full_clean()
    event.save(update_fields=[*event_values.keys(), "updated_at"] if event_values else ["updated_at"])

    if "venue" in fields:
        rows = list(_event_occurrences(event, for_update=True))
        if occurrence is not None:
            rows = [occurrence]
        for row in rows:
            _set_occurrence_place(event=event, occurrence=row)
    if "capacity" in fields:
        if occurrence is None:
            rows = list(_event_occurrences(event, for_update=True)[:2])
            if len(rows) != 1:
                raise ValidationError("Choisissez explicitement la date dont vous modifiez la capacité.")
            occurrence = rows[0]
        _set_event_capacity(event=event, occurrence=occurrence, total_quantity=fields["capacity"])
    if {"registration_start_at", "registration_end_at"} & fields.keys():
        _clamp_offer_windows(event)
    return event


@transaction.atomic
def publish_event(*, event: Event, actor) -> Event:
    _ensure_can_manage(actor, event)
    if event.status != EventStatus.DRAFT:
        raise ValidationError("Seul un brouillon peut être publié.")
    occurrences = list(_event_occurrences(event, for_update=True))
    viable = [row for row in occurrences if row.status == OccurrenceStatus.DRAFT and not _occurrence_is_past(row)]
    if not viable:
        raise ValidationError("Un événement doit posséder au moins une date actuelle ou future pour être publié.")
    event.full_clean()
    _clamp_offer_windows(event)
    update_activity_common(activity=event.activity, status=ActivityStatus.PUBLISHED)
    for occurrence in viable:
        set_occurrence_status(occurrence=occurrence, status=OccurrenceStatus.SCHEDULED)
    for offer in event.activity.offers.select_for_update().filter(status=OfferStatus.DRAFT):
        update_offer(offer=offer, status=OfferStatus.ACTIVE)
    event.published_at = timezone.now()
    event.cancelled_at = None
    event.save(update_fields=["published_at", "cancelled_at", "updated_at"])
    return event


@transaction.atomic
def cancel_event_occurrence(*, event: Event, occurrence, actor):
    _ensure_can_manage(actor, event)
    if occurrence.activity_id != event.activity_id:
        raise ValidationError("Cette date n’appartient pas à cet événement.")
    return set_occurrence_status(occurrence=occurrence, status=OccurrenceStatus.CANCELLED)


@transaction.atomic
def cancel_event(*, event: Event, actor) -> Event:
    _ensure_can_manage(actor, event)
    if event.status not in {EventStatus.DRAFT, EventStatus.PUBLISHED}:
        raise ValidationError("Seul un brouillon ou un événement publié peut être annulé.")
    update_activity_common(activity=event.activity, status=ActivityStatus.CANCELLED)
    for occurrence in _event_occurrences(event, for_update=True):
        if occurrence.status in {OccurrenceStatus.DRAFT, OccurrenceStatus.SCHEDULED}:
            set_occurrence_status(occurrence=occurrence, status=OccurrenceStatus.CANCELLED)
    event.cancelled_at = timezone.now()
    event.save(update_fields=["cancelled_at", "updated_at"])
    return event


@transaction.atomic
def complete_event(*, event: Event, actor) -> Event:
    _ensure_can_manage(actor, event)
    if event.status != EventStatus.PUBLISHED:
        raise ValidationError("Seul un événement publié peut être terminé.")
    occurrences = list(_event_occurrences(event, for_update=True))
    if any(row.status == OccurrenceStatus.SCHEDULED and not _occurrence_is_past(row) for row in occurrences):
        raise ValidationError("L’événement possède encore une date actuelle ou future.")
    update_activity_common(activity=event.activity, status=ActivityStatus.COMPLETED)
    for occurrence in occurrences:
        if occurrence.status == OccurrenceStatus.SCHEDULED:
            complete_occurrence(occurrence=occurrence)
    event.save(update_fields=["updated_at"])
    return event


@transaction.atomic
def reopen_event(*, event: Event, actor) -> Event:
    _ensure_can_manage(actor, event)
    event = Event.objects.select_for_update().select_related("activity").get(pk=event.pk)
    if event.status != EventStatus.COMPLETED:
        raise ValidationError("Seul un événement terminé peut être réouvert.")
    occurrences = list(_event_occurrences(event, for_update=True))
    reopenable = [row for row in occurrences if row.status == OccurrenceStatus.COMPLETED and not _occurrence_is_past(row)]
    if not reopenable:
        raise ValidationError("Aucune date future n’est réouvrable ; ajoutez une nouvelle date au lieu de modifier l’historique.")

    before = {"status": event.status, "occurrence_ids": [str(row.pk) for row in reopenable]}
    reopen_completed_activity(activity=event.activity)
    for occurrence in reopenable:
        reopen_completed_occurrence(occurrence=occurrence)
    event.save(update_fields=["updated_at"])

    from operations.services import audit_action

    audit_action(
        actor=actor,
        action="event.reopened",
        target_type="event",
        target_id=event.pk,
        summary=f"Réouverture de {event.title} après une clôture prématurée.",
        before=before,
        after={"status": event.status, "occurrence_ids": [str(row.pk) for row in reopenable]},
        metadata={"activity_id": str(event.activity_id)},
    )
    return event
