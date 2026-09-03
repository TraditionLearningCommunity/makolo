# Generated manually for Makolo Intelligence I2.

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0004_service_opportunity_notification_preferences"),
        ("organizations", "0004_profilefollow"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderConnection",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("protocol", models.CharField(choices=[("openai_compatible", "OpenAI-compatible")], max_length=32)),
                ("base_url", models.URLField(max_length=500)),
                ("default_model", models.CharField(max_length=160)),
                ("scope", models.CharField(choices=[("platform", "Plateforme"), ("space", "Espace"), ("profile", "Profil")], default="platform", max_length=16)),
                ("enabled", models.BooleanField(default=False)),
                ("priority", models.PositiveSmallIntegerField(default=100)),
                ("timeout_seconds", models.PositiveSmallIntegerField(default=8)),
                ("health_status", models.CharField(choices=[("unknown", "Inconnu"), ("healthy", "Disponible"), ("degraded", "Dégradé"), ("unavailable", "Indisponible"), ("invalid_credentials", "Clé invalide")], default="unknown", max_length=24)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="intelligence_provider_connections", to="accounts.userprofile")),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="intelligence_provider_connections", to="organizations.organization")),
            ],
            options={"ordering": ["priority", "name", "id"]},
        ),
        migrations.CreateModel(
            name="ProviderCredential",
            fields=[
                ("connection", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="credential", serialize=False, to="intelligence.providerconnection")),
                ("encrypted_secret", models.TextField()),
                ("key_hint", models.CharField(blank=True, max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="IntelligenceRoute",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("capability", models.CharField(choices=[("text_generate", "text_generate"), ("structured_generate", "structured_generate"), ("embed", "embed"), ("rerank", "rerank")], max_length=32)),
                ("model", models.CharField(blank=True, max_length=160)),
                ("priority", models.PositiveSmallIntegerField(default=100)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("connection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="routes", to="intelligence.providerconnection")),
            ],
            options={"ordering": ["priority", "id"]},
        ),
        migrations.AddIndex(model_name="providerconnection", index=models.Index(fields=["enabled", "scope", "priority"], name="intel_conn_route_idx")),
        migrations.AddIndex(model_name="providerconnection", index=models.Index(fields=["health_status"], name="intel_conn_health_idx")),
        migrations.AddConstraint(model_name="providerconnection", constraint=models.CheckConstraint(condition=models.Q(("timeout_seconds__gte", 1)), name="intel_conn_timeout_positive")),
        migrations.AddConstraint(
            model_name="providerconnection",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("profile__isnull", True), ("scope", "platform"), ("space__isnull", True))
                    | models.Q(("profile__isnull", True), ("scope", "space"), ("space__isnull", False))
                    | models.Q(("profile__isnull", False), ("scope", "profile"), ("space__isnull", True))
                ),
                name="intel_conn_scope_target_valid",
            ),
        ),
        migrations.AddConstraint(model_name="intelligenceroute", constraint=models.UniqueConstraint(fields=("capability", "connection"), name="intel_route_capability_connection_unique")),
        migrations.AddIndex(model_name="intelligenceroute", index=models.Index(fields=["capability", "enabled", "priority"], name="intel_route_lookup_idx")),
    ]
