import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0004_occurrence_temporal_schedule"),
        ("journeys", "0005_journey_plan_templates"),
        ("requirements", "0002_trusted_reuse_application"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RequirementDefinition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(max_length=120)),
                ("version", models.PositiveIntegerField(default=1)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("mode", models.CharField(choices=[("automatic", "Automatic"), ("action", "Action"), ("verification", "Verification"), ("external_check", "External check"), ("payment", "Payment"), ("review", "Review")], default="verification", max_length=24)),
                ("evaluator_key", models.CharField(blank=True, max_length=120)),
                ("evaluator_config", models.JSONField(blank=True, default=dict)),
                ("is_mandatory", models.BooleanField(default=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publié"), ("retired", "Retiré")], default="draft", max_length=16)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirement_definitions", to="activities.activity")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_requirement_definitions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["activity", "key", "version"]},
        ),
        migrations.CreateModel(
            name="JourneyRequirementAssessment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("state", models.CharField(choices=[("unassessed", "Unassessed"), ("pending", "Pending"), ("satisfied", "Satisfied"), ("unsatisfied", "Unsatisfied"), ("not_applicable", "Not applicable")], default="unassessed", max_length=24)),
                ("reason_code", models.CharField(blank=True, max_length=160)),
                ("note", models.TextField(blank=True)),
                ("observed_at", models.DateTimeField(blank=True, null=True)),
                ("assessed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assessed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journey_requirement_assessments", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirement_assessments", to="journeys.journey")),
                ("journey_step", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="requirement_assessments", to="journeys.journeystep")),
                ("requirement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journey_assessments", to="requirements.requirementdefinition")),
            ],
            options={"ordering": ["journey", "requirement__position", "requirement_id"]},
        ),
        migrations.AddConstraint(
            model_name="requirementdefinition",
            constraint=models.UniqueConstraint(fields=("activity", "key", "version"), name="req_definition_version_unique"),
        ),
        migrations.AddConstraint(
            model_name="requirementdefinition",
            constraint=models.CheckConstraint(condition=models.Q(version__gt=0), name="req_definition_version_positive"),
        ),
        migrations.AddConstraint(
            model_name="requirementdefinition",
            constraint=models.UniqueConstraint(condition=models.Q(status="published"), fields=("activity", "key"), name="req_definition_one_published"),
        ),
        migrations.AddIndex(
            model_name="requirementdefinition",
            index=models.Index(fields=["activity", "status", "position"], name="req_def_activity_state_idx"),
        ),
        migrations.AddConstraint(
            model_name="journeyrequirementassessment",
            constraint=models.UniqueConstraint(fields=("journey", "requirement"), name="req_journey_assessment_unique"),
        ),
        migrations.AddIndex(
            model_name="journeyrequirementassessment",
            index=models.Index(fields=["journey", "state"], name="req_journey_state_idx"),
        ),
    ]
