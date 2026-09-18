from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prospector_storage", "0004_safety_budget"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProspectorFeedbackEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_key", models.CharField(max_length=160, unique=True)),
                ("target_key", models.CharField(db_index=True, max_length=96)),
                ("signal", models.CharField(max_length=40)),
                ("producer", models.CharField(max_length=40)),
                ("source_ref", models.CharField(max_length=255)),
                ("occurred_at", models.DateTimeField()),
                ("scopes", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "prospector_feedback_event",
                "ordering": ["id"],
                "indexes": [
                    models.Index(
                        fields=["target_key", "occurred_at", "id"],
                        name="pros_fb_event_target_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ProspectorFeedbackProjection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("policy_key", models.CharField(max_length=120)),
                ("policy_fingerprint", models.CharField(max_length=64)),
                ("last_event_id", models.PositiveBigIntegerField(default=0)),
                ("projected_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "prospector_feedback_projection",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("policy_key", "policy_fingerprint"),
                        name="pros_fb_projection_uq",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ProspectorFeedbackStat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("policy_fingerprint", models.CharField(max_length=64)),
                ("scope_kind", models.CharField(max_length=32)),
                ("scope_key", models.CharField(max_length=255)),
                ("sample_count", models.PositiveBigIntegerField(default=0)),
                ("score_sum", models.BigIntegerField(default=0)),
                ("positive_count", models.PositiveBigIntegerField(default=0)),
                ("neutral_count", models.PositiveBigIntegerField(default=0)),
                ("negative_count", models.PositiveBigIntegerField(default=0)),
                ("last_feedback_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "prospector_feedback_stat",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("policy_fingerprint", "scope_kind", "scope_key"),
                        name="pros_fb_stat_scope_uq",
                    )
                ],
                "indexes": [
                    models.Index(
                        fields=["policy_fingerprint", "scope_kind", "scope_key"],
                        name="pros_fb_stat_scope_idx",
                    )
                ],
            },
        ),
    ]
