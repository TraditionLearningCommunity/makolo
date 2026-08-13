import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from activities.models import Activity, ActivityStatus, Occurrence, OccurrencePlace, OccurrencePlaceRole, OccurrenceStatus
from activities.services import attach_occurrence_place

from .models import Event, EventStatus, EventVenue


BRIDGE_NAMESPACE = uuid.UUID("c72bc780-36d3-4ee0-8f8d-e0a0a173086c")


def _stable_id(kind, event_id):
    return uuid.uuid5(BRIDGE_NAMESPACE, f"event:{event_id}:{kind}")


def _activity_status(event_status):
    return {EventStatus.DRAFT: ActivityStatus.DRAFT, EventStatus.PUBLISHED: ActivityStatus.PUBLISHED, EventStatus.CANCELLED: ActivityStatus.CANCELLED, EventStatus.COMPLETED: ActivityStatus.COMPLETED}[event_status]


def _occurrence_status(event_status):
    return {EventStatus.DRAFT: OccurrenceStatus.DRAFT, EventStatus.PUBLISHED: OccurrenceStatus.SCHEDULED, EventStatus.CANCELLED: OccurrenceStatus.CANCELLED, EventStatus.COMPLETED: OccurrenceStatus.COMPLETED}[event_status]


def ensure_event_activity(event: Event) -> Activity:
    if not event.pk:
        raise ValidationError("L’Event doit être enregistré avant de créer son Activity.")
    if event.activity_id:
        return Activity.objects.get(pk=event.activity_id)
    activity = Activity.objects.filter(pk=_stable_id("activity", event.pk)).first()
    if activity is None:
        activity = Activity(id=_stable_id("activity", event.pk), space_id=event.organization_id, created_by_id=event.organizer_id, title=event.title, short_description=event.short_description, description=event.description, status=_activity_status(event.status), visibility=event.visibility)
        activity.save()
    Event.objects.filter(pk=event.pk).update(activity_id=activity.pk)
    event.activity = activity
    return activity


def sync_event_activity(event: Event) -> Activity:
    activity = ensure_event_activity(event)
    activity.space_id = event.organization_id
    activity.created_by_id = event.organizer_id
    activity.title = event.title
    activity.short_description = event.short_description
    activity.description = event.description
    activity.status = _activity_status(event.status)
    activity.visibility = event.visibility
    activity.save(update_fields=["space", "created_by", "title", "short_description", "description", "status", "visibility", "updated_at"])
    return activity


def sync_event_occurrence(event: Event, *, activity=None) -> Occurrence:
    activity = activity or sync_event_activity(event)
    occurrence, _ = Occurrence.objects.get_or_create(pk=_stable_id("occurrence", event.pk), defaults={"activity": activity, "start_at": event.start_at, "end_at": event.end_at, "timezone": event.timezone, "status": _occurrence_status(event.status)})
    occurrence.activity = activity
    occurrence.start_at = event.start_at
    occurrence.end_at = event.end_at
    occurrence.timezone = event.timezone
    occurrence.status = _occurrence_status(event.status)
    occurrence.save(update_fields=["activity", "start_at", "end_at", "timezone", "status", "updated_at"])
    return occurrence


def sync_event_occurrence_place(event: Event, *, occurrence=None):
    occurrence = occurrence or sync_event_occurrence(event)
    place = None
    if event.venue_id:
        venue = EventVenue.objects.select_related("place").filter(pk=event.venue_id).first()
        if venue and venue.place_id:
            place = venue.place
    if place is None:
        OccurrencePlace.objects.filter(occurrence=occurrence, role=OccurrencePlaceRole.PRIMARY).delete()
        return None
    return attach_occurrence_place(occurrence=occurrence, place=place, role=OccurrencePlaceRole.PRIMARY)


@transaction.atomic
def sync_event_core(event: Event):
    activity = sync_event_activity(event)
    occurrence = sync_event_occurrence(event, activity=activity)
    sync_event_occurrence_place(event, occurrence=occurrence)
    return activity, occurrence
