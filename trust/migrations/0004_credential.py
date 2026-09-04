import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("trust", "0003_private_evidence_storage"),
    ]

    operations = [
        migrations.CreateModel(
            name="Credential",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("credential_type", models.CharField(choices=[("participation", "Attestation de participation"), ("completion", "Certificat de complétion"), ("attestation", "Autre attestation")], max_length=24)),
                ("title", models.CharField(max_length=220)),
                ("statement", models.TextField(blank=True, max_length=3000)),
                ("status", models.CharField(choices=[("issued", "Valide"), ("revoked", "Révoquée")], default="issued", max_length=12)),
                ("issued_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoke_reason", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trust_credentials", to="activities.activity")),
                ("issuer_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="issued_trust_credentials_as_profile", to=settings.AUTH_USER_MODEL)),
                ("issuer_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="issued_trust_credentials", to="organizations.organization")),
                ("issued_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="issued_trust_credentials_audit", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_credentials", to="journeys.journey")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_credentials", to="activities.occurrence")),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="revoked_trust_credentials", to=settings.AUTH_USER_MODEL)),
                ("subject_profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trust_credentials", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-issued_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="credential",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("issuer_profile__isnull", True), ("issuer_space__isnull", False))
                    | models.Q(("issuer_profile__isnull", False), ("issuer_space__isnull", True))
                ),
                name="trust_cred_exactly_one_issuer",
            ),
        ),
        migrations.AddConstraint(
            model_name="credential",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("revoked_at__isnull", True), ("revoked_by__isnull", True), ("status", "issued"))
                    | models.Q(("revoked_at__isnull", False), ("revoked_by__isnull", False), ("status", "revoked"))
                ),
                name="trust_cred_revocation_state",
            ),
        ),
        migrations.AddIndex(model_name="credential", index=models.Index(fields=["subject_profile", "status"], name="trust_cred_subject_idx")),
        migrations.AddIndex(model_name="credential", index=models.Index(fields=["issuer_space", "status"], name="trust_cred_space_idx")),
        migrations.AddIndex(model_name="credential", index=models.Index(fields=["issuer_profile", "status"], name="trust_cred_profile_idx")),
        migrations.AddIndex(model_name="credential", index=models.Index(fields=["public_id", "status"], name="trust_cred_public_idx")),
    ]
