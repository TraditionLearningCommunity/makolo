import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("activities", "0001_initial"),
        ("journeys", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Access",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("valid", "Valide"), ("used", "Utilisé"), ("cancelled", "Annulé"), ("revoked", "Révoqué"), ("expired", "Expiré"), ("transferred", "Transféré")], default="pending", max_length=16)),
                ("single_use", models.BooleanField(default=True)),
                ("source_key", models.CharField(blank=True, help_text="Clé d’idempotence métier dans la Démarche (ex. ticket:<uuid>).", max_length=180)),
                ("valid_from", models.DateTimeField(blank=True, null=True)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="access_rights", to="activities.activity")),
                ("beneficiary", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="access_rights", to=settings.AUTH_USER_MODEL)),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_access_rights", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accesses", to="journeys.journey")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="access_rights", to="activities.occurrence")),
            ],
            options={
                "ordering": ["-created_at", "id"],
                "indexes": [
                    models.Index(fields=["beneficiary", "status"], name="access_beneficiary_status_idx"),
                    models.Index(fields=["activity", "status"], name="access_activity_status_idx"),
                    models.Index(fields=["occurrence", "status"], name="access_occurrence_status_idx"),
                    models.Index(fields=["valid_until"], name="access_valid_until_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=Q(("valid_from__isnull", True), ("valid_until__isnull", True), ("valid_until__gt", models.F("valid_from")), _connector="OR"), name="access_valid_window"),
                    models.UniqueConstraint(condition=Q(("journey__isnull", False), models.Q(("source_key", ""), _negated=True)), fields=("journey", "source_key"), name="access_journey_source_unique"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AccessCredential",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("credential_type", models.CharField(choices=[("qr", "QR"), ("barcode", "Code-barres"), ("pass", "Pass"), ("digital_badge", "Badge numérique")], default="qr", max_length=24)),
                ("status", models.CharField(choices=[("active", "Actif"), ("revoked", "Révoqué"), ("expired", "Expiré")], default="active", max_length=16)),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("issued_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("expired_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("access", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="credentials", to="access.access")),
            ],
            options={
                "ordering": ["access", "-version", "-issued_at"],
                "indexes": [
                    models.Index(fields=["access", "status"], name="access_credential_status_idx"),
                    models.Index(fields=["public_id", "version"], name="access_credential_lookup_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("access", "version"), name="access_credential_version_unique")],
            },
        ),
        migrations.CreateModel(
            name="AccessUse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("result", models.CharField(choices=[("accepted", "Accepté"), ("already_used", "Déjà utilisé"), ("expired", "Expiré"), ("not_yet_valid", "Pas encore valide"), ("revoked", "Révoqué"), ("cancelled", "Annulé"), ("wrong_activity", "Mauvaise Activity"), ("wrong_occurrence", "Mauvaise Occurrence"), ("invalid_credential", "Credential invalide")], max_length=32)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("used_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("access", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uses", to="access.access")),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="access_uses_controlled", to=settings.AUTH_USER_MODEL)),
                ("credential", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uses", to="access.accesscredential")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="access_uses", to="activities.occurrence")),
            ],
            options={
                "ordering": ["-used_at", "id"],
                "indexes": [
                    models.Index(fields=["access", "used_at"], name="access_use_access_time_idx"),
                    models.Index(fields=["occurrence", "used_at"], name="access_use_occurrence_time_idx"),
                ],
            },
        ),
    ]
