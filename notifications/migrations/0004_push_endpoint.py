from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_service_opportunity_categories"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PushEndpoint",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[("fcm", "Firebase Cloud Messaging")],
                        default="fcm",
                        max_length=16,
                    ),
                ),
                (
                    "platform",
                    models.CharField(
                        choices=[("android", "Android"), ("ios", "iOS")],
                        max_length=16,
                    ),
                ),
                ("installation_id", models.CharField(max_length=128)),
                ("token_hash", models.CharField(max_length=64)),
                ("encrypted_token", models.TextField()),
                ("token_hint", models.CharField(blank=True, max_length=24)),
                ("app_version", models.CharField(blank=True, max_length=64)),
                ("active", models.BooleanField(default=True)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="push_endpoints",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["user", "active"],
                        name="push_endpoint_user_active_idx",
                    ),
                    models.Index(
                        fields=["provider", "active"],
                        name="push_endpoint_provider_active_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("provider", "installation_id"),
                        name="push_endpoint_unique_installation",
                    ),
                    models.UniqueConstraint(
                        fields=("provider", "token_hash"),
                        name="push_endpoint_unique_token",
                    ),
                ],
            },
        ),
    ]
