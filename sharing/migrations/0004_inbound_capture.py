from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import journeys.storage
import sharing.inbound_models


class Migration(migrations.Migration):
    dependencies = [
        ("journeys", "0003_services_core_journey_collaboration"),
        ("sharing", "0003_journey_share_reuse"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InboundCapture",
            fields=[
                ("id", models.UUIDField(default=__import__("uuid").uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_kind", models.CharField(choices=[("url", "Lien"), ("text", "Texte"), ("file", "Fichier")], max_length=12)),
                ("status", models.CharField(choices=[("pending", "À classer"), ("absorbed", "Ajouté"), ("discarded", "Ignoré"), ("expired", "Expiré")], default="pending", max_length=12)),
                ("source_url", models.URLField(blank=True, max_length=2048)),
                ("text", models.TextField(blank=True)),
                ("file", models.FileField(blank=True, max_length=500, storage=journeys.storage.private_artifact_storage, upload_to=sharing.inbound_models.inbound_capture_upload_to)),
                ("original_filename", models.CharField(blank=True, max_length=180)),
                ("mime_type", models.CharField(blank=True, max_length=180)),
                ("size", models.PositiveBigIntegerField(default=0)),
                ("expires_at", models.DateTimeField(default=sharing.inbound_models.default_capture_expiry)),
                ("absorbed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("absorbed_artifact", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inbound_capture_origin", to="journeys.journeyartifact")),
                ("absorbed_note", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inbound_capture_origin", to="journeys.journeynote")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inbound_captures", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.AddIndex(model_name="inboundcapture", index=models.Index(fields=["created_by", "status", "created_at"], name="sharing_capture_owner_idx")),
        migrations.AddIndex(model_name="inboundcapture", index=models.Index(fields=["status", "expires_at"], name="sharing_capture_expiry_idx")),
    ]
