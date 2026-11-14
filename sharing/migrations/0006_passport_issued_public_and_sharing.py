import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("sharing", "0005_public_identifier_passport_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="passportsnapshot",
            name="public_at_issue",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="shareenvelope",
            name="subject_type",
            field=models.CharField(
                max_length=24,
                choices=[
                    ("activity", "Activity"),
                    ("opportunity", "Opportunity"),
                    ("journey", "Journey"),
                    ("passport", "Passeport émis"),
                ],
            ),
        ),
        migrations.CreateModel(
            name="PassportShareSubject",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        primary_key=True, default=uuid.uuid4,
                        editable=False, serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "envelope",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="passport_subject",
                        to="sharing.shareenvelope",
                    ),
                ),
                (
                    "snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="passport_share_subjects",
                        to="sharing.passportsnapshot",
                    ),
                ),
            ],
        ),
    ]
