from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ProspectorFrontierEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_key", models.CharField(max_length=96, unique=True)),
                ("kind", models.CharField(max_length=64)),
                ("locator", models.TextField()),
                ("status", models.CharField(choices=[("ready", "Ready"), ("claimed", "Claimed"), ("completed", "Completed"), ("suppressed", "Suppressed")], default="ready", max_length=16)),
                ("priority", models.PositiveIntegerField(default=100)),
                ("available_at", models.DateTimeField(db_index=True)),
                ("first_discovered_at", models.DateTimeField()),
                ("last_discovered_at", models.DateTimeField()),
                ("discovery_count", models.PositiveBigIntegerField(default=1)),
                ("policy_context", models.JSONField(blank=True, default=dict)),
                ("observation_hints", models.JSONField(blank=True, default=dict)),
                ("claim_token", models.UUIDField(blank=True, db_index=True, null=True)),
                ("claimed_by", models.CharField(blank=True, max_length=120)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "prospector_frontier_entry",
                "ordering": ["priority", "available_at", "id"],
                "indexes": [
                    models.Index(fields=["status", "available_at", "priority", "id"], name="pros_frontier_ready_idx"),
                    models.Index(fields=["last_discovered_at", "id"], name="pros_frontier_seen_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("discovery_count__gte", 1)), name="pros_frontier_count_gte_1"),
                    models.CheckConstraint(
                        condition=(
                            models.Q(
                                ("claim_token__isnull", False),
                                ("claimed_at__isnull", False),
                                ("lease_expires_at__isnull", False),
                                ("status", "claimed"),
                            )
                            | (
                                ~models.Q(("status", "claimed"))
                                & models.Q(
                                    ("claim_token__isnull", True),
                                    ("claimed_at__isnull", True),
                                    ("claimed_by", ""),
                                    ("lease_expires_at__isnull", True),
                                )
                            )
                        ),
                        name="pros_frontier_claim_consistent",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(("completed_at__isnull", False), ("status", "completed"))
                            | ~models.Q(("status", "completed"))
                        ),
                        name="pros_frontier_completed_at",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProspectorFrontierEvidence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("evidence_key", models.CharField(max_length=64)),
                ("method", models.CharField(max_length=80)),
                ("source_target_key", models.CharField(blank=True, max_length=128)),
                ("source_observation_ref", models.CharField(blank=True, max_length=255)),
                ("provider", models.CharField(blank=True, max_length=160)),
                ("attributes", models.JSONField(blank=True, default=dict)),
                ("policy_context", models.JSONField(blank=True, default=dict)),
                ("observation_hints", models.JSONField(blank=True, default=dict)),
                ("first_discovered_at", models.DateTimeField()),
                ("last_discovered_at", models.DateTimeField()),
                ("discovery_count", models.PositiveBigIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("frontier_entry", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence_rows", to="prospector_storage.prospectorfrontierentry")),
            ],
            options={
                "db_table": "prospector_frontier_evidence",
                "ordering": ["first_discovered_at", "id"],
                "indexes": [
                    models.Index(fields=["source_target_key", "id"], name="pros_evidence_source_idx")
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("frontier_entry", "evidence_key"), name="pros_evidence_entry_key_uq"),
                    models.CheckConstraint(condition=models.Q(("discovery_count__gte", 1)), name="pros_evidence_count_gte_1"),
                ],
            },
        ),
    ]
