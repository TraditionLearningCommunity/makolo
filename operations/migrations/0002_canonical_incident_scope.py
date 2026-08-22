import uuid

import django.db.models.deletion
from django.db import migrations, models


EVENT_ACTIVITY_NAMESPACE = uuid.UUID("c72bc780-36d3-4ee0-8f8d-e0a0a173086c")


def stable_event_projection_id(kind, event_id):
    return uuid.uuid5(EVENT_ACTIVITY_NAMESPACE, f"event:{event_id}:{kind}")


def backfill_incident_scope(apps, schema_editor):
    OperationsIncident = apps.get_model("operations", "OperationsIncident")
    Activity = apps.get_model("activities", "Activity")
    Occurrence = apps.get_model("activities", "Occurrence")

    incidents = OperationsIncident.objects.exclude(event_id=None).select_related("event")
    for incident in incidents.iterator():
        event = incident.event
        activity_id = getattr(event, "activity_id", None)
        if not activity_id:
            continue

        # events.0005 creates one deterministic canonical Occurrence per legacy
        # Event. Do not read Event.start_at/end_at here: events.0007 removes
        # those historical columns before this migration can run on some
        # existing databases (for example the PythonAnywhere beta database).
        occurrence = (
            Occurrence.objects.filter(
                pk=stable_event_projection_id("occurrence", event.pk),
                activity_id=activity_id,
            )
            .order_by("id")
            .first()
        )

        incident.activity_id = activity_id
        incident.occurrence_id = occurrence.pk if occurrence else None
        if not incident.organization_id:
            incident.organization_id = (
                Activity.objects.filter(pk=activity_id)
                .values_list("space_id", flat=True)
                .first()
            )
        incident.save(update_fields=["activity_id", "occurrence_id", "organization_id"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0002_occurrence_place"),
        ("events", "0005_backfill_activity_occurrence"),
        ("operations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="operationsincident",
            name="activity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="operations_incidents",
                to="activities.activity",
            ),
        ),
        migrations.AddField(
            model_name="operationsincident",
            name="occurrence",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="operations_incidents",
                to="activities.occurrence",
            ),
        ),
        migrations.AlterField(
            model_name="operationsincident",
            name="event",
            field=models.ForeignKey(
                blank=True,
                help_text="Projection Events historique; Operations utilise Activity/Occurrence comme contexte canonique.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="operations_incidents",
                to="events.event",
            ),
        ),
        migrations.RunPython(backfill_incident_scope, noop),
        migrations.AddIndex(
            model_name="operationsincident",
            index=models.Index(fields=["activity", "status"], name="ops_inc_activity_idx"),
        ),
        migrations.AddIndex(
            model_name="operationsincident",
            index=models.Index(fields=["occurrence", "status"], name="ops_inc_occurrence_idx"),
        ),
    ]
