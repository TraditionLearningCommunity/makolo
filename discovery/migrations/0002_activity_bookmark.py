import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    EventBookmark = apps.get_model("discovery", "EventBookmark")
    ActivityBookmark = apps.get_model("discovery", "ActivityBookmark")
    seen = set()
    for bookmark in EventBookmark.objects.select_related("event").order_by("created_at", "id"):
        key = (bookmark.user_id, bookmark.event.activity_id)
        if key in seen:
            continue
        seen.add(key)
        migrated, _ = ActivityBookmark.objects.get_or_create(
            user_id=bookmark.user_id,
            activity_id=bookmark.event.activity_id,
            defaults={"id": bookmark.id},
        )
        ActivityBookmark.objects.filter(pk=migrated.pk).update(created_at=bookmark.created_at)


def backwards(apps, schema_editor):
    ActivityBookmark = apps.get_model("discovery", "ActivityBookmark")
    EventBookmark = apps.get_model("discovery", "EventBookmark")
    Event = apps.get_model("events", "Event")
    event_by_activity = {
        activity_id: event_id
        for activity_id, event_id in Event.objects.values_list("activity_id", "id")
    }
    for bookmark in ActivityBookmark.objects.order_by("created_at", "id"):
        event_id = event_by_activity.get(bookmark.activity_id)
        if not event_id:
            continue
        restored, _ = EventBookmark.objects.get_or_create(
            user_id=bookmark.user_id,
            event_id=event_id,
            defaults={"id": bookmark.id},
        )
        EventBookmark.objects.filter(pk=restored.pk).update(created_at=bookmark.created_at)


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0003_activity_owner_profile"),
        ("events", "0007_cutover_event_to_activity"),
        ("discovery", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityBookmark",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bookmarks",
                        to="activities.activity",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activity_bookmarks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="activitybookmark",
            constraint=models.UniqueConstraint(
                fields=("user", "activity"),
                name="disc_bm_user_activity_uq",
            ),
        ),
        migrations.AddIndex(
            model_name="activitybookmark",
            index=models.Index(fields=["user", "created_at"], name="disc_bm_user_created_idx"),
        ),
        migrations.AddIndex(
            model_name="activitybookmark",
            index=models.Index(fields=["activity", "created_at"], name="disc_bm_activity_created_idx"),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.DeleteModel(name="EventBookmark"),
    ]
