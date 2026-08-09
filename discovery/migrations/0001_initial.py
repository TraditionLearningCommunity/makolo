import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("events", "0002_event_organization"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventBookmark",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookmarks", to="events.event")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_bookmarks", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="eventbookmark",
            constraint=models.UniqueConstraint(fields=("user", "event"), name="discovery_bookmark_user_event_unique"),
        ),
        migrations.AddIndex(
            model_name="eventbookmark",
            index=models.Index(fields=["user", "created_at"], name="disc_bookmark_user_idx"),
        ),
        migrations.AddIndex(
            model_name="eventbookmark",
            index=models.Index(fields=["event", "created_at"], name="disc_bookmark_event_idx"),
        ),
    ]
