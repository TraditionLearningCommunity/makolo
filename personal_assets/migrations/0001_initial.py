import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import journeys.collaboration_models
import journeys.storage


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("journeys", "0003_services_core_journey_collaboration"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonalAsset",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("cv", "CV"), ("cover_letter", "Lettre de motivation"), ("certificate", "Certificat"), ("transcript", "Relevé"), ("recommendation", "Recommandation"), ("identity_document", "Document d’identité"), ("form", "Formulaire"), ("payment_receipt", "Reçu de paiement"), ("other", "Autre")], default="other", max_length=32)),
                ("title", models.CharField(max_length=220)),
                ("sensitivity", models.CharField(choices=[("normal", "Normale"), ("sensitive", "Sensible"), ("restricted", "Restreinte")], default="normal", max_length=16)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("controller", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="personal_assets", to=settings.AUTH_USER_MODEL)),
                ("subject_external_beneficiary", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="personal_assets", to="journeys.externalbeneficiary")),
                ("subject_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="personal_assets_as_subject", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="PersonalAssetVersion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.PositiveIntegerField(default=1)),
                ("file", models.FileField(max_length=500, storage=journeys.storage.private_artifact_storage, upload_to=journeys.collaboration_models.journey_artifact_upload_to)),
                ("mime_type", models.CharField(max_length=180)),
                ("size", models.PositiveBigIntegerField()),
                ("content_hash", models.CharField(max_length=64)),
                ("issued_at", models.DateField(blank=True, null=True)),
                ("expires_at", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="personal_assets.personalasset")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_personal_asset_versions", to=settings.AUTH_USER_MODEL)),
                ("supersedes", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="superseded_by", to="personal_assets.personalassetversion")),
            ],
            options={"ordering": ["asset", "version", "created_at"]},
        ),
        migrations.AddConstraint(model_name="personalasset", constraint=models.CheckConstraint(condition=models.Q(models.Q(("subject_external_beneficiary__isnull", True), ("subject_profile__isnull", False)), models.Q(("subject_external_beneficiary__isnull", False), ("subject_profile__isnull", True)), _connector="OR"), name="personal_asset_subject_xor")),
        migrations.AddIndex(model_name="personalasset", index=models.Index(fields=["controller", "archived_at"], name="pers_asset_ctrl_arch_idx")),
        migrations.AddConstraint(model_name="personalassetversion", constraint=models.UniqueConstraint(fields=("asset", "version"), name="personal_asset_version_unique")),
        migrations.AddConstraint(model_name="personalassetversion", constraint=models.CheckConstraint(condition=models.Q(("version__gte", 1)), name="personal_asset_version_positive")),
        migrations.AddIndex(model_name="personalassetversion", index=models.Index(fields=["asset", "version"], name="pers_asset_ver_idx")),
        migrations.AddIndex(model_name="personalassetversion", index=models.Index(fields=["content_hash"], name="pers_asset_hash_idx")),
    ]
