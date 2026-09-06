import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import geography.validators


def backfill_occurrence_parts(apps, schema_editor):
    Occurrence = apps.get_model("activities", "Occurrence")
    for occurrence in Occurrence.objects.exclude(start_at__isnull=True).iterator():
        zone = ZoneInfo(occurrence.timezone or "Africa/Lubumbashi")
        local_start = occurrence.start_at.astimezone(zone)
        occurrence.start_date = local_start.date()
        occurrence.start_time = local_start.timetz().replace(tzinfo=None)
        occurrence.timing_kind = "exact"
        if occurrence.end_at:
            local_end = occurrence.end_at.astimezone(zone)
            occurrence.end_date = local_end.date()
            occurrence.end_time = local_end.timetz().replace(tzinfo=None)
        occurrence.save(update_fields=["start_date", "start_time", "end_date", "end_time", "timing_kind"])


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0003_activity_owner_profile"),
    ]

    operations = [
        migrations.CreateModel(
            name="OccurrenceSchedule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("label", models.CharField(blank=True, max_length=180)),
                ("timezone", models.CharField(default="Africa/Lubumbashi", max_length=100, validators=[geography.validators.validate_timezone_name])),
                ("frequency", models.CharField(choices=[("daily", "Tous les jours"), ("weekly", "Chaque semaine"), ("monthly", "Chaque mois"), ("yearly", "Chaque année")], max_length=16)),
                ("interval", models.PositiveSmallIntegerField(default=1)),
                ("starts_on", models.DateField()),
                ("ends_on", models.DateField(blank=True, null=True)),
                ("timing_kind", models.CharField(choices=[("exact", "Date et heure exactes"), ("date_only", "Date connue, heure à confirmer"), ("all_day", "Toute la journée")], default="exact", max_length=16)),
                ("start_time", models.TimeField(blank=True, null=True)),
                ("duration_minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("month_day", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("month", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("occurrence_status", models.CharField(choices=[("draft", "Brouillon"), ("scheduled", "Planifiée"), ("cancelled", "Annulée"), ("completed", "Terminée")], default="scheduled", max_length=20)),
                ("status", models.CharField(choices=[("active", "Actif"), ("paused", "En pause"), ("retired", "Retiré")], default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="occurrence_schedules", to="activities.activity")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_occurrence_schedules", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["activity_id", "starts_on", "start_time", "id"]},
        ),
        migrations.CreateModel(
            name="OccurrenceScheduleWeekday",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("weekday", models.PositiveSmallIntegerField(help_text="0=lundi … 6=dimanche")),
                ("schedule", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="weekdays", to="activities.occurrenceschedule")),
            ],
            options={"ordering": ["weekday", "id"]},
        ),
        migrations.AddField(model_name="occurrence", name="start_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="occurrence", name="start_time", field=models.TimeField(blank=True, null=True)),
        migrations.AddField(model_name="occurrence", name="end_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="occurrence", name="end_time", field=models.TimeField(blank=True, null=True)),
        migrations.AddField(model_name="occurrence", name="timing_kind", field=models.CharField(choices=[("exact", "Date et heure exactes"), ("date_only", "Date connue, heure à confirmer"), ("all_day", "Toute la journée")], default="exact", max_length=16)),
        migrations.AddField(model_name="occurrence", name="schedule", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="generated_occurrences", to="activities.occurrenceschedule")),
        migrations.AddField(model_name="occurrence", name="schedule_local_date", field=models.DateField(blank=True, null=True)),
        migrations.AlterField(model_name="occurrence", name="start_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterModelOptions(name="occurrence", options={"ordering": ["start_date", "start_time", "id"]}),
        migrations.RunPython(backfill_occurrence_parts, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name="occurrence", name="activities_occ_end_after_start"),
        migrations.RemoveIndex(model_name="occurrence", name="activities_occ_activity_idx"),
        migrations.RemoveIndex(model_name="occurrence", name="activities_occ_status_idx"),
        migrations.AddConstraint(
            model_name="occurrence",
            constraint=models.CheckConstraint(
                condition=models.Q(end_date__isnull=True) | models.Q(start_date__isnull=True) | models.Q(end_date__gte=models.F("start_date")),
                name="activities_occ_date_window",
            ),
        ),
        migrations.AddConstraint(
            model_name="occurrence",
            constraint=models.UniqueConstraint(
                condition=models.Q(schedule__isnull=False),
                fields=("schedule", "schedule_local_date"),
                name="activities_occ_schedule_slot_unique",
            ),
        ),
        migrations.AddIndex(model_name="occurrence", index=models.Index(fields=["activity", "start_date", "start_time"], name="activities_occ_activity_idx")),
        migrations.AddIndex(model_name="occurrence", index=models.Index(fields=["status", "start_date", "start_time"], name="activities_occ_status_idx")),
        migrations.AddIndex(model_name="occurrence", index=models.Index(fields=["start_at"], name="activities_occ_startat_idx")),
        migrations.AddConstraint(model_name="occurrenceschedule", constraint=models.CheckConstraint(condition=models.Q(interval__gt=0), name="activities_sched_interval_pos")),
        migrations.AddConstraint(model_name="occurrenceschedule", constraint=models.CheckConstraint(condition=models.Q(ends_on__isnull=True) | models.Q(ends_on__gte=models.F("starts_on")), name="activities_sched_window_valid")),
        migrations.AddIndex(model_name="occurrenceschedule", index=models.Index(fields=["activity", "status"], name="activities_sched_activity_idx")),
        migrations.AddIndex(model_name="occurrenceschedule", index=models.Index(fields=["status", "starts_on", "ends_on"], name="activities_sched_window_idx")),
        migrations.AddConstraint(model_name="occurrencescheduleweekday", constraint=models.UniqueConstraint(fields=("schedule", "weekday"), name="activities_sched_weekday_unique")),
        migrations.AddConstraint(model_name="occurrencescheduleweekday", constraint=models.CheckConstraint(condition=models.Q(weekday__gte=0, weekday__lte=6), name="activities_sched_weekday_valid")),
    ]
