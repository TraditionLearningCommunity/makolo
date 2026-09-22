from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("observer_storage", "0003_http_scope_runtime")]
    operations = [
        migrations.CreateModel(
            name="InterpretationRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("interpretation_ref", models.CharField(max_length=255, unique=True)),
                ("observation_ref", models.CharField(db_index=True, max_length=255)),
                ("material_key", models.CharField(max_length=255)),
                ("target_key", models.CharField(db_index=True, max_length=96)),
                ("strategy_key", models.CharField(max_length=120)),
                ("strategy_version", models.CharField(max_length=80)),
                ("strategy_fingerprint", models.CharField(max_length=128)),
                ("lifecycle", models.CharField(choices=[("pending","pending"),("processing","processing"),("finalized","finalized")], default="pending", max_length=16)),
                ("outcome", models.CharField(blank=True, choices=[("interpreted","interpreted"),("partial","partial"),("no_useful_information","no_useful_information"),("failed","failed")], max_length=32)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("failure_code", models.CharField(blank=True, max_length=120)),
                ("warning_codes", models.JSONField(blank=True, default=list)),
                ("stats", models.JSONField(blank=True, default=dict)),
                ("claim_token", models.UUIDField(blank=True, db_index=True, null=True)),
                ("claimed_by", models.CharField(blank=True, max_length=120)),
                ("lease_expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("prospector_reported_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table":"interpreter_run","ordering":["created_at","id"],
                "indexes":[
                    models.Index(fields=["lifecycle","lease_expires_at","id"], name="int_run_lease_idx"),
                    models.Index(fields=["observation_ref","strategy_fingerprint"], name="int_run_observation_idx"),
                ],
                "constraints":[
                    models.UniqueConstraint(fields=("material_key","strategy_fingerprint"), name="int_run_material_strategy_uq"),
                    models.CheckConstraint(
                        condition=(
                            models.Q(lifecycle="pending", claim_token__isnull=True, claimed_by="", lease_expires_at__isnull=True, outcome="", started_at__isnull=True, completed_at__isnull=True)
                            | (models.Q(lifecycle="processing", claim_token__isnull=False, lease_expires_at__isnull=False, started_at__isnull=False, completed_at__isnull=True, outcome="") & ~models.Q(claimed_by=""))
                            | (models.Q(lifecycle="finalized", claim_token__isnull=True, claimed_by="", lease_expires_at__isnull=True, started_at__isnull=False, completed_at__isnull=False) & ~models.Q(outcome=""))
                        ),
                        name="int_run_lifecycle_consistent",
                    ),
                    models.CheckConstraint(
                        condition=(models.Q(outcome="failed") & ~models.Q(failure_code="")) | (~models.Q(outcome="failed") & models.Q(failure_code="")),
                        name="int_run_failure_consistent",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="InterpretationCandidate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("candidate_ref", models.CharField(max_length=255, unique=True)),
                ("ordinal", models.PositiveIntegerField()),
                ("kind", models.CharField(choices=[("entity","entity"),("fact","fact"),("relation","relation"),("constraint","constraint")], max_length=24)),
                ("payload", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="candidate_rows", to="interpreter_storage.interpretationrun")),
            ],
            options={
                "db_table":"interpreter_candidate","ordering":["run","ordinal"],
                "indexes":[models.Index(fields=["run","kind","ordinal"], name="int_candidate_kind_idx")],
                "constraints":[
                    models.UniqueConstraint(fields=("run","ordinal"), name="int_candidate_ordinal_uq"),
                    models.CheckConstraint(condition=models.Q(ordinal__gte=1), name="int_candidate_ordinal_gte_1"),
                ],
            },
        ),
        migrations.CreateModel(
            name="InterpretationArtifactUse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ordinal", models.PositiveIntegerField()),
                ("artifact_ref", models.CharField(max_length=255)),
                ("artifact_observation_ref", models.CharField(max_length=255)),
                ("role", models.CharField(max_length=64)),
                ("media_type", models.CharField(blank=True, max_length=180)),
                ("content_digest", models.CharField(max_length=64)),
                ("selection_reason", models.CharField(max_length=120)),
                ("completeness", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="artifact_use_rows", to="interpreter_storage.interpretationrun")),
            ],
            options={
                "db_table":"interpreter_artifact_use","ordering":["run","ordinal"],
                "indexes":[models.Index(fields=["artifact_ref","id"], name="int_artifact_ref_idx")],
                "constraints":[
                    models.UniqueConstraint(fields=("run","ordinal"), name="int_artifact_use_ordinal_uq"),
                    models.UniqueConstraint(fields=("run","artifact_ref"), name="int_artifact_use_ref_uq"),
                    models.CheckConstraint(condition=models.Q(ordinal__gte=1), name="int_artifact_use_ordinal_gte_1"),
                ],
            },
        ),
    ]
