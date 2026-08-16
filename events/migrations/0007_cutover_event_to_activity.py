import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0006_validate_canonical_event_core"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="event",
            name="event_end_after_start",
        ),
        migrations.RemoveIndex(
            model_name="event",
            name="events_even_organiz_b26406_idx",
        ),
        migrations.AlterField(
            model_name="event",
            name="activity",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="event_vertical",
                to="activities.activity",
            ),
        ),
        migrations.RemoveField(model_name="event", name="organization"),
        migrations.RemoveField(model_name="event", name="organizer"),
        migrations.RemoveField(model_name="event", name="title"),
        migrations.RemoveField(model_name="event", name="short_description"),
        migrations.RemoveField(model_name="event", name="description"),
        migrations.RemoveField(model_name="event", name="status"),
        migrations.RemoveField(model_name="event", name="visibility"),
        migrations.RemoveField(model_name="event", name="start_at"),
        migrations.RemoveField(model_name="event", name="end_at"),
        migrations.RemoveField(model_name="event", name="timezone"),
        migrations.RemoveField(model_name="event", name="capacity"),
        migrations.AlterModelOptions(
            name="event",
            options={
                "ordering": ["created_at", "id"],
                "verbose_name": "événement",
                "verbose_name_plural": "événements",
            },
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["activity", "created_at"], name="events_activity_created_idx"),
        ),
        migrations.AlterModelOptions(
            name="eventvenue",
            options={
                "ordering": ["name", "id"],
                "verbose_name": "lieu d’événement",
                "verbose_name_plural": "lieux d’événements",
            },
        ),
    ]
