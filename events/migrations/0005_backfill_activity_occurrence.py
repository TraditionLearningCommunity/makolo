import uuid
from django.db import migrations
from django.utils.text import slugify

NAMESPACE = uuid.UUID("c72bc780-36d3-4ee0-8f8d-e0a0a173086c")

def stable_id(kind, event_id):
    return uuid.uuid5(NAMESPACE, f"event:{event_id}:{kind}")

def backfill_event_core(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    EventVenue = apps.get_model("events", "EventVenue")
    Activity = apps.get_model("activities", "Activity")
    Occurrence = apps.get_model("activities", "Occurrence")
    OccurrencePlace = apps.get_model("activities", "OccurrencePlace")
    occurrence_status = {"draft":"draft", "published":"scheduled", "cancelled":"cancelled", "completed":"completed"}
    for event in Event.objects.all().iterator():
        activity, _ = Activity.objects.update_or_create(pk=stable_id("activity", event.pk), defaults={"space_id":event.organization_id,"created_by_id":event.organizer_id,"title":event.title,"slug":(event.slug or slugify(event.title) or "activite")[:240],"short_description":event.short_description,"description":event.description,"status":event.status,"visibility":event.visibility})
        Event.objects.filter(pk=event.pk).update(activity_id=activity.pk)
        occurrence, _ = Occurrence.objects.update_or_create(pk=stable_id("occurrence", event.pk), defaults={"activity_id":activity.pk,"label":"","start_at":event.start_at,"end_at":event.end_at,"timezone":event.timezone,"status":occurrence_status[event.status]})
        place_id = EventVenue.objects.filter(pk=event.venue_id).values_list("place_id", flat=True).first() if event.venue_id else None
        primary = OccurrencePlace.objects.filter(occurrence_id=occurrence.pk, role="primary")
        if place_id:
            link = primary.first()
            if link:
                primary.exclude(pk=link.pk).delete()
                link.place_id = place_id
                link.position = 0
                link.save(update_fields=["place", "position", "updated_at"])
            else:
                OccurrencePlace.objects.create(occurrence_id=occurrence.pk, place_id=place_id, role="primary", position=0)
        else:
            primary.delete()

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [("events", "0004_event_activity")]
    operations = [migrations.RunPython(backfill_event_core, noop)]
