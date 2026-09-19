from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prospector_storage", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProspectorSourceCheckpoint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_name", models.CharField(max_length=120)),
                ("mission_key", models.CharField(max_length=160)),
                ("mission_fingerprint", models.CharField(max_length=64)),
                ("source_revision", models.CharField(max_length=120)),
                ("cursor", models.JSONField(blank=True, default=dict)),
                ("exhausted", models.BooleanField(default=False)),
                ("checkpoint_updated_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "prospector_source_checkpoint",
                "indexes": [
                    models.Index(fields=["source_name", "exhausted", "updated_at"], name="pros_source_progress_idx")
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("source_name", "mission_key"), name="pros_source_checkpoint_uq")
                ],
            },
        ),
    ]
