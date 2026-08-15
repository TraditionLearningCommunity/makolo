from django.db import migrations, models
import django.db.models.deletion


def backfill_assignment_scope(apps, schema_editor):
    ScannerAssignment = apps.get_model("scanner", "ScannerAssignment")
    Occurrence = apps.get_model("activities", "Occurrence")

    assignments = ScannerAssignment.objects.exclude(event_id=None).select_related("event")
    for assignment in assignments.iterator():
        event = assignment.event
        activity_id = getattr(event, "activity_id", None)
        if not activity_id:
            continue
        occurrence = (
            Occurrence.objects.filter(
                activity_id=activity_id,
                start_at=event.start_at,
                end_at=event.end_at,
            )
            .order_by("id")
            .first()
        )
        assignment.activity_id = activity_id
        assignment.occurrence_id = occurrence.pk if occurrence else None
        assignment.save(update_fields=["activity_id", "occurrence_id"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0002_occurrence_place"),
        ("events", "0005_backfill_activity_occurrence"),
        ("scanner", "0002_eventaccessgate_smart_access"),
    ]

    operations = [
        migrations.AddField(
            model_name="scannerassignment",
            name="activity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="scanner_assignments",
                to="activities.activity",
            ),
        ),
        migrations.AddField(
            model_name="scannerassignment",
            name="occurrence",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="scanner_assignments",
                to="activities.occurrence",
            ),
        ),
        migrations.AlterField(
            model_name="scannerassignment",
            name="event",
            field=models.ForeignKey(
                blank=True,
                help_text="Projection Events historique; le scope canonique est Activity/Occurrence.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="scanner_assignments",
                to="events.event",
            ),
        ),
        migrations.RunPython(backfill_assignment_scope, noop),
        migrations.RemoveConstraint(
            model_name="scannerassignment",
            name="scanner_unique_event_agent",
        ),
        migrations.RemoveIndex(
            model_name="scannerassignment",
            name="scanner_assign_event_idx",
        ),
        migrations.AddConstraint(
            model_name="scannerassignment",
            constraint=models.CheckConstraint(
                condition=models.Q(activity__isnull=False) | models.Q(event__isnull=False),
                name="scanner_assignment_has_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="scannerassignment",
            constraint=models.UniqueConstraint(
                condition=models.Q(activity__isnull=False, occurrence__isnull=True),
                fields=("activity", "agent"),
                name="scanner_unique_activity_agent",
            ),
        ),
        migrations.AddConstraint(
            model_name="scannerassignment",
            constraint=models.UniqueConstraint(
                condition=models.Q(activity__isnull=False, occurrence__isnull=False),
                fields=("activity", "occurrence", "agent"),
                name="scanner_unique_occ_agent",
            ),
        ),
        migrations.AddIndex(
            model_name="scannerassignment",
            index=models.Index(fields=["activity", "is_active"], name="scanner_assign_activity_idx"),
        ),
        migrations.AddIndex(
            model_name="scannerassignment",
            index=models.Index(fields=["occurrence", "is_active"], name="scanner_assign_occ_idx"),
        ),
        migrations.AlterModelOptions(
            name="scannerassignment",
            options={
                "ordering": ["activity__title", "occurrence__start_at", "label", "agent__username"],
                "verbose_name": "affectation scanner",
                "verbose_name_plural": "affectations scanner",
            },
        ),
    ]
