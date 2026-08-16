import uuid

from django.db import migrations
from django.utils.text import slugify


NAMESPACE = uuid.UUID("c72bc780-36d3-4ee0-8f8d-e0a0a173086c")


def stable_id(kind, event_id):
    return uuid.uuid5(NAMESPACE, f"event:{event_id}:{kind}")


def validate_and_finish_event_core(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    EventVenue = apps.get_model("events", "EventVenue")
    Activity = apps.get_model("activities", "Activity")
    Occurrence = apps.get_model("activities", "Occurrence")
    OccurrencePlace = apps.get_model("activities", "OccurrencePlace")

    occurrence_status = {
        "draft": "draft",
        "published": "scheduled",
        "cancelled": "cancelled",
        "completed": "completed",
        "archived": "completed",
    }

    for event in Event.objects.all().iterator():
        activity = None
        if event.activity_id:
            activity = Activity.objects.filter(pk=event.activity_id).first()
        if activity is None:
            activity, _ = Activity.objects.update_or_create(
                pk=stable_id("activity", event.pk),
                defaults={
                    "space_id": event.organization_id,
                    "created_by_id": event.organizer_id,
                    "title": event.title,
                    "slug": (event.slug or slugify(event.title) or "activite")[:240],
                    "short_description": event.short_description,
                    "description": event.description,
                    "status": event.status,
                    "visibility": event.visibility,
                },
            )
            Event.objects.filter(pk=event.pk).update(activity_id=activity.pk)

        occurrence = Occurrence.objects.filter(
            activity_id=activity.pk,
            pk=stable_id("occurrence", event.pk),
        ).first()
        if occurrence is None:
            occurrence = Occurrence.objects.filter(activity_id=activity.pk).order_by("start_at", "id").first()
        if occurrence is None:
            occurrence = Occurrence.objects.create(
                id=stable_id("occurrence", event.pk),
                activity_id=activity.pk,
                label="",
                start_at=event.start_at,
                end_at=event.end_at,
                timezone=event.timezone,
                status=occurrence_status.get(event.status, "draft"),
            )

        place_id = None
        if event.venue_id:
            place_id = EventVenue.objects.filter(pk=event.venue_id).values_list("place_id", flat=True).first()
        if place_id:
            primary = OccurrencePlace.objects.filter(occurrence_id=occurrence.pk, role="primary").order_by("id")
            link = primary.first()
            if link:
                primary.exclude(pk=link.pk).delete()
                if link.place_id != place_id or link.position != 0:
                    link.place_id = place_id
                    link.position = 0
                    link.save(update_fields=["place", "position", "updated_at"])
            else:
                OccurrencePlace.objects.create(
                    occurrence_id=occurrence.pk,
                    place_id=place_id,
                    role="primary",
                    position=0,
                )

    if Event.objects.filter(activity_id__isnull=True).exists():
        raise RuntimeError("Task 9 cutover requires every Event to have an Activity.")

    activity_ids = set(Event.objects.values_list("activity_id", flat=True))
    missing_occurrences = [
        activity_id
        for activity_id in activity_ids
        if not Occurrence.objects.filter(activity_id=activity_id).exists()
    ]
    if missing_occurrences:
        raise RuntimeError("Task 9 cutover requires every Event Activity to have an Occurrence.")

    invalid_venues = EventVenue.objects.filter(kind__in=["physical", "hybrid"], place_id__isnull=True)
    if invalid_venues.exists():
        raise RuntimeError("Physical/hybrid EventVenue rows must have a canonical Place before Task 9 cutover.")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0005_backfill_activity_occurrence"),
        ("activities", "0002_occurrence_place"),
    ]

    operations = [
        migrations.RunPython(validate_and_finish_event_core, noop),
    ]
