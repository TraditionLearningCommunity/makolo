import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("activities", "0003_activity_owner_profile"),
    ]

    operations = [
        migrations.CreateModel(
            name="Topic",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["label", "code"]},
        ),
        migrations.CreateModel(
            name="ProfileInterest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_public", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile_interests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "topic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="profile_interests",
                        to="topics.topic",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="ActivityTopic",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="topic_links",
                        to="activities.activity",
                    ),
                ),
                (
                    "topic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="activity_links",
                        to="topics.topic",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="topic",
            index=models.Index(fields=["is_active", "label"], name="topic_active_label_idx"),
        ),
        migrations.AddConstraint(
            model_name="profileinterest",
            constraint=models.UniqueConstraint(fields=("profile", "topic"), name="topics_profile_interest_unique"),
        ),
        migrations.AddIndex(
            model_name="profileinterest",
            index=models.Index(fields=["profile", "is_public"], name="topic_pi_prof_public_idx"),
        ),
        migrations.AddConstraint(
            model_name="activitytopic",
            constraint=models.UniqueConstraint(fields=("activity", "topic"), name="topics_activity_topic_unique"),
        ),
        migrations.AddIndex(
            model_name="activitytopic",
            index=models.Index(fields=["topic", "activity"], name="topic_at_topic_act_idx"),
        ),
    ]
