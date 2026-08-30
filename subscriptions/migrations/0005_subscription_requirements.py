import uuid

from django.db import migrations, models
import django.db.models.deletion

import subscriptions.models


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0004_default_bases_and_backfill"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanRequirement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=120, validators=[subscriptions.models.technical_code_validator])),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("phase", models.CharField(choices=[("acquisition", "Acquisition"), ("ongoing", "Ongoing"), ("renewal", "Renewal")], max_length=16)),
                ("mode", models.CharField(choices=[("automatic", "Automatic"), ("action", "Action"), ("verification", "Verification"), ("external_check", "External check"), ("payment", "Payment"), ("review", "Review")], max_length=20)),
                ("evaluator_key", models.CharField(blank=True, max_length=160)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("is_mandatory", models.BooleanField(default=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("failure_policy", models.CharField(choices=[("block", "Block"), ("deny", "Deny"), ("warn", "Warn"), ("grace", "Grace"), ("suspend", "Suspend")], max_length=16)),
                ("grace_period_days", models.PositiveIntegerField(blank=True, null=True)),
                ("disclosure", models.CharField(choices=[("visible", "Visible"), ("generic", "Generic"), ("internal", "Internal")], default="visible", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirements", to="subscriptions.planversion")),
            ],
            options={"ordering": ["plan_version", "phase", "position", "key"]},
        ),
        migrations.CreateModel(
            name="EntitlementRequirement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=120, validators=[subscriptions.models.technical_code_validator])),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("mode", models.CharField(choices=[("automatic", "Automatic"), ("action", "Action"), ("verification", "Verification"), ("external_check", "External check"), ("payment", "Payment"), ("review", "Review")], max_length=20)),
                ("evaluator_key", models.CharField(blank=True, max_length=160)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("is_mandatory", models.BooleanField(default=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("disclosure", models.CharField(choices=[("visible", "Visible"), ("generic", "Generic"), ("internal", "Internal")], default="visible", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan_entitlement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirements", to="subscriptions.planentitlement")),
            ],
            options={"ordering": ["plan_entitlement", "position", "key"]},
        ),
        migrations.AddConstraint(
            model_name="planrequirement",
            constraint=models.UniqueConstraint(fields=("plan_version", "key"), name="subs_plan_requirement_key_unique"),
        ),
        migrations.AddConstraint(
            model_name="planrequirement",
            constraint=models.UniqueConstraint(fields=("plan_version", "phase", "position"), name="subs_plan_requirement_position_unique"),
        ),
        migrations.AddIndex(
            model_name="planrequirement",
            index=models.Index(fields=["plan_version", "phase", "is_mandatory"], name="subs_plan_req_phase_idx"),
        ),
        migrations.AddIndex(
            model_name="planrequirement",
            index=models.Index(fields=["evaluator_key"], name="subs_plan_req_eval_idx"),
        ),
        migrations.AddConstraint(
            model_name="entitlementrequirement",
            constraint=models.UniqueConstraint(fields=("plan_entitlement", "key"), name="subs_ent_requirement_key_unique"),
        ),
        migrations.AddConstraint(
            model_name="entitlementrequirement",
            constraint=models.UniqueConstraint(fields=("plan_entitlement", "position"), name="subs_ent_requirement_position_unique"),
        ),
        migrations.AddIndex(
            model_name="entitlementrequirement",
            index=models.Index(fields=["evaluator_key"], name="subs_ent_req_eval_idx"),
        ),
    ]
