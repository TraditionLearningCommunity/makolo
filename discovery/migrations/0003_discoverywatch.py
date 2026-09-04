import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0002_activity_bookmark"),
        ("objectives", "0004_project_projectdossierlink"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DiscoveryWatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=140)),
                ("status", models.CharField(choices=[("active", "Active"), ("paused", "En pause")], default="active", max_length=16)),
                ("criteria", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("dossier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="discovery_watches", to="objectives.dossier")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="discovery_watches", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="discoverywatch",
            index=models.Index(fields=["owner", "status", "updated_at"], name="disc_watch_owner_state_idx"),
        ),
    ]
