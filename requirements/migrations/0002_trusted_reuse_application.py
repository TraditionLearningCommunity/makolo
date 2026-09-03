import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("journeys", "0003_services_core_journey_collaboration"),
        ("personal_assets", "0002_q2_controlled_reuse"),
        ("requirements", "0001_trusted_reuse_policy"),
        ("services", "0004_horizontal_requirement_states"),
        ("trust", "0003_private_evidence_storage"),
    ]

    operations = [
        migrations.CreateModel(
            name="RequirementReuseApplication",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_type", models.CharField(choices=[("library", "Ma Bibliothèque"), ("journey_artifact", "JourneyArtifact historique"), ("proof", "Proof Trust")], max_length=24)),
                ("decision", models.CharField(max_length=40)),
                ("reason_codes", models.JSONField(default=list)),
                ("freshness", models.CharField(blank=True, max_length=32)),
                ("sensitivity", models.CharField(blank=True, max_length=16)),
                ("source_status", models.CharField(blank=True, max_length=32)),
                ("source_version", models.PositiveIntegerField(blank=True, null=True)),
                ("confirmation_confirmed", models.BooleanField(default=False)),
                ("materialization_path", models.CharField(blank=True, max_length=80)),
                ("observed_at", models.DateTimeField()),
                ("applied_at", models.DateTimeField(auto_now_add=True)),
                ("applied_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="requirement_reuse_applications", to=settings.AUTH_USER_MODEL)),
                ("assessment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trusted_reuse_applications", to="services.servicerequirementassessment")),
                ("evidence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trusted_reuse_applications", to="services.servicerequirementevidence")),
                ("intermediate_asset_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="intermediate_requirement_reuse_applications", to="personal_assets.personalassetversion")),
                ("materialized_artifact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trusted_reuse_materializations", to="journeys.journeyartifact")),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="applications", to="requirements.requirementreusepolicy")),
                ("source_asset_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="requirement_reuse_applications", to="personal_assets.personalassetversion")),
                ("source_journey_artifact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="source_requirement_reuse_applications", to="journeys.journeyartifact")),
                ("source_proof", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="requirement_reuse_applications", to="trust.proof")),
            ],
            options={"ordering": ["-applied_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="requirementreuseapplication",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("source_asset_version__isnull", False), ("source_journey_artifact__isnull", True), ("source_proof__isnull", True))
                    | models.Q(("source_asset_version__isnull", True), ("source_journey_artifact__isnull", False), ("source_proof__isnull", True))
                    | models.Q(("source_asset_version__isnull", True), ("source_journey_artifact__isnull", True), ("source_proof__isnull", False))
                ),
                name="req_reuse_app_one_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="requirementreuseapplication",
            constraint=models.UniqueConstraint(condition=models.Q(("source_asset_version__isnull", False)), fields=("assessment", "source_asset_version"), name="req_reuse_app_asset_unique"),
        ),
        migrations.AddConstraint(
            model_name="requirementreuseapplication",
            constraint=models.UniqueConstraint(condition=models.Q(("source_journey_artifact__isnull", False)), fields=("assessment", "source_journey_artifact"), name="req_reuse_app_art_unique"),
        ),
        migrations.AddConstraint(
            model_name="requirementreuseapplication",
            constraint=models.UniqueConstraint(condition=models.Q(("source_proof__isnull", False)), fields=("assessment", "source_proof"), name="req_reuse_app_proof_unique"),
        ),
        migrations.AddIndex(
            model_name="requirementreuseapplication",
            index=models.Index(fields=["assessment", "applied_at"], name="req_reuse_app_assess_idx"),
        ),
        migrations.AddIndex(
            model_name="requirementreuseapplication",
            index=models.Index(fields=["policy", "applied_at"], name="req_reuse_app_policy_idx"),
        ),
    ]
