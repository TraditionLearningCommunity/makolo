import uuid

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("journeys", "0003_services_core_journey_collaboration"),
        ("sharing", "0002_sharedelivery"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shareenvelope",
            name="subject_type",
            field=models.CharField(
                choices=[("activity", "Activity"), ("opportunity", "Opportunity"), ("journey", "Journey")],
                max_length=24,
            ),
        ),
        migrations.CreateModel(
            name="JourneyShareSubject",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("snapshot", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "envelope",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="journey_subject",
                        to="sharing.shareenvelope",
                    ),
                ),
                (
                    "source_journey",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="share_subjects",
                        to="journeys.journey",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="JourneyShareAcceptance",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("accepted_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "delivery",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="journey_acceptance",
                        to="sharing.sharedelivery",
                    ),
                ),
                (
                    "resulting_journey",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="share_origin",
                        to="journeys.journey",
                    ),
                ),
            ],
            options={"ordering": ["-accepted_at", "id"]},
        ),
    ]
