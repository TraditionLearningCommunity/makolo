import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import sharing.inbound_models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("sharing", "0007_space_document_sharing"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InboundCaptureBundle",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("request_key", models.CharField(max_length=64)),
                ("payload_digest", models.CharField(max_length=64)),
                ("text", models.TextField(blank=True)),
                ("links", models.JSONField(default=list, blank=True)),
                ("context", models.JSONField(default=dict, blank=True)),
                ("expires_at", models.DateTimeField(default=sharing.inbound_models.default_capture_expiry)),
                ("received_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name="inbound_capture_bundles")),
                ("space", models.ForeignKey(to="organizations.organization", on_delete=django.db.models.deletion.CASCADE, null=True, blank=True, related_name="inbound_capture_bundles")),
                ("captures", models.ManyToManyField(to="sharing.inboundcapture", blank=True, related_name="bundles")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["created_by", "received_at"], name="sharing_bundle_owner_received_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=["created_by", "request_key"], name="sharing_bundle_owner_request_uniq"),
                ],
            },
        ),
    ]
