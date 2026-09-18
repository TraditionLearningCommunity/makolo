from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prospector_storage", "0003_handoff_generation"),
    ]

    operations = [
        migrations.AddField(
            model_name="prospectorfrontierentry",
            name="suppressed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prospectorfrontierentry",
            name="suppression_reason",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddConstraint(
            model_name="prospectorfrontierentry",
            constraint=models.CheckConstraint(
                condition=(
                    (
                        models.Q(
                            ("status", "suppressed"),
                            ("suppressed_at__isnull", False),
                        )
                        & ~models.Q(("suppression_reason", ""))
                    )
                    | (
                        ~models.Q(("status", "suppressed"))
                        & models.Q(
                            ("suppressed_at__isnull", True),
                            ("suppression_reason", ""),
                        )
                    )
                ),
                name="pros_frontier_suppression_consistent",
            ),
        ),
        migrations.CreateModel(
            name="ProspectorBudgetCounter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("policy_key", models.CharField(max_length=120)),
                ("scope_kind", models.CharField(max_length=32)),
                ("scope_key", models.CharField(max_length=255)),
                ("period_start", models.DateTimeField()),
                ("period_end", models.DateTimeField()),
                ("used_count", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "prospector_budget_counter",
                "indexes": [
                    models.Index(fields=["policy_key", "period_end", "scope_kind"], name="pros_budget_counter_period_idx")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("policy_key", "scope_kind", "scope_key", "period_start"),
                        name="pros_budget_counter_scope_uq",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ProspectorBudgetReservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("handoff_key", models.CharField(max_length=96)),
                ("policy_key", models.CharField(max_length=120)),
                ("period_start", models.DateTimeField()),
                ("period_end", models.DateTimeField()),
                ("scopes", models.JSONField(default=dict)),
                ("reserved_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "prospector_budget_reservation",
                "indexes": [
                    models.Index(fields=["policy_key", "period_end"], name="pros_budget_reservation_period_idx")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("handoff_key", "policy_key", "period_start"),
                        name="pros_budget_reservation_uq",
                    )
                ],
            },
        ),
    ]
