from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("interpreter_storage", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="ResolutionRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("resolution_ref", models.CharField(max_length=255, unique=True)),
                ("interpretation_ref", models.CharField(db_index=True, max_length=255)),
                ("material_key", models.CharField(max_length=255)),
                ("observation_ref", models.CharField(db_index=True, max_length=255)),
                ("target_key", models.CharField(db_index=True, max_length=96)),
                ("strategy_key", models.CharField(max_length=120)),
                ("strategy_version", models.CharField(max_length=80)),
                ("strategy_fingerprint", models.CharField(max_length=128)),
                ("lifecycle", models.CharField(choices=[("pending","pending"),("processing","processing"),("finalized","finalized")], default="pending", max_length=16)),
                ("outcome", models.CharField(blank=True, choices=[("resolved","resolved"),("partial","partial"),("ambiguous","ambiguous"),("conflict","conflict"),("unresolved","unresolved"),("failed","failed")], max_length=32)),
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
                "db_table": "resolver_run",
                "ordering": ["created_at", "id"],
                "indexes": [
                    models.Index(fields=["lifecycle","lease_expires_at","id"], name="res_run_lease_idx"),
                    models.Index(fields=["interpretation_ref","strategy_fingerprint"], name="res_run_interp_idx"),
                    models.Index(fields=["target_key","completed_at"], name="res_run_target_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("interpretation_ref","strategy_fingerprint"), name="res_run_interp_strategy_uq"),
                    models.CheckConstraint(
                        condition=(
                            models.Q(lifecycle="pending", claim_token__isnull=True, claimed_by="", lease_expires_at__isnull=True, outcome="", started_at__isnull=True, completed_at__isnull=True)
                            | (models.Q(lifecycle="processing", claim_token__isnull=False, lease_expires_at__isnull=False, started_at__isnull=False, completed_at__isnull=True, outcome="") & ~models.Q(claimed_by=""))
                            | (models.Q(lifecycle="finalized", claim_token__isnull=True, claimed_by="", lease_expires_at__isnull=True, started_at__isnull=False, completed_at__isnull=False) & ~models.Q(outcome=""))
                        ),
                        name="res_run_lifecycle_consistent",
                    ),
                    models.CheckConstraint(
                        condition=(models.Q(outcome="failed") & ~models.Q(failure_code="")) | (~models.Q(outcome="failed") & models.Q(failure_code="")),
                        name="res_run_failure_consistent",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ResolutionAssertionRow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assertion_ref", models.CharField(max_length=255, unique=True)),
                ("ordinal", models.PositiveIntegerField()),
                ("candidate_ref", models.CharField(db_index=True, max_length=255)),
                ("kind", models.CharField(choices=[("entity","entity"),("fact","fact"),("relation","relation"),("constraint","constraint"),("conflict","conflict")], max_length=24)),
                ("status", models.CharField(choices=[("matched","matched"),("new_candidate","new_candidate"),("ambiguous","ambiguous"),("unresolved","unresolved"),("rejected","rejected"),("linked","linked"),("partial","partial"),("conflict","conflict"),("update","update")], max_length=24)),
                ("canonical_domain", models.CharField(blank=True, max_length=120)),
                ("canonical_object_ref", models.CharField(blank=True, max_length=255)),
                ("predicate", models.CharField(blank=True, max_length=120)),
                ("subject_key", models.CharField(blank=True, max_length=400)),
                ("object_key", models.CharField(blank=True, max_length=400)),
                ("semantic_fingerprint", models.CharField(blank=True, max_length=128)),
                ("payload", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assertion_rows", to="resolver_storage.resolutionrun")),
            ],
            options={
                "db_table": "resolver_assertion",
                "ordering": ["run","ordinal"],
                "indexes": [
                    models.Index(fields=["run","kind","ordinal"], name="res_assertion_kind_idx"),
                    models.Index(fields=["canonical_domain","canonical_object_ref","predicate"], name="res_assertion_fact_lookup_idx"),
                    models.Index(fields=["subject_key","predicate"], name="res_assertion_subject_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("run","ordinal"), name="res_assertion_ordinal_uq"),
                    models.CheckConstraint(condition=models.Q(ordinal__gte=1), name="res_assertion_ordinal_gte_1"),
                    models.CheckConstraint(
                        condition=models.Q(canonical_domain="", canonical_object_ref="") | (~models.Q(canonical_domain="") & ~models.Q(canonical_object_ref="")),
                        name="res_assertion_canonical_pair",
                    ),
                ],
            },
        ),
    ]
