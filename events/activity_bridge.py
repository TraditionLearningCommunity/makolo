from django.core.exceptions import ValidationError
from django.db import transaction

from activities.models import OccurrencePlace, OccurrencePlaceRole
from activities.services import attach_occurrence_place

from .models import Event, EventVenue, VenueKind


def ensure_event_activity(event: Event):
    """Compatibility accessor: Task 9 makes Event.activity mandatory."""
    if not event.activity_id:
        raise ValidationError("Cet Event legacy ne possède pas d’Activity canonique.")
    return event.activity


def sync_event_activity(event: Event):
    """Deprecated compatibility name; generic data only flows from Activity."""
    return ensure_event_activity(event)


def sync_event_occurrence(event: Event, *, activity=None):
    """Deprecated compatibility name returning the Event primary Occurrence."""
    activity = activity or ensure_event_activity(event)
    occurrence = activity.occurrences.order_by("start_at", "id").first()
    if occurrence is None:
        raise ValidationError("Cet Event ne possède pas d’Occurrence canonique.")
    return occurrence


def sync_event_occurrence_place(event: Event, *, occurrence=None):
    """Keep only the legitimate EventVenue -> OccurrencePlace projection.

    Geography fields are never copied from EventVenue. A physical/hybrid Event
    may project its already-canonical ``EventVenue.place`` onto the primary
    occurrence. Online Events remove the physical primary link.
    """
    occurrence = occurrence or sync_event_occurrence(event)
    venue = None
    if event.venue_id:
        venue = EventVenue.objects.select_related("place").filter(pk=event.venue_id).first()
    if not venue or venue.kind == VenueKind.ONLINE:
        OccurrencePlace.objects.filter(
            occurrence=occurrence,
            role=OccurrencePlaceRole.PRIMARY,
        ).delete()
        return None
    if not venue.place_id:
        raise ValidationError("Un EventVenue physique/hybride doit référencer un Place canonique.")
    return attach_occurrence_place(
        occurrence=occurrence,
        place=venue.place,
        role=OccurrencePlaceRole.PRIMARY,
        position=0,
    )


@transaction.atomic
def sync_event_core(event: Event):
    """Temporary import-compatible adapter; it no longer synchronizes generic data."""
    activity = ensure_event_activity(event)
    occurrence = sync_event_occurrence(event, activity=activity)
    sync_event_occurrence_place(event, occurrence=occurrence)
    return activity, occurrence
