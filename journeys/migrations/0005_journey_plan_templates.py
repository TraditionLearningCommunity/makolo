import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0004_occurrence_temporal_schedule"),
        ("journeys", "0004_fulfillment_workflow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="JourneyPlanTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(max_length=120)),
                ("version", models.PositiveIntegerField(default=1)),
                ("name", models.CharField(max_length=220)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publié"), ("retired", "Retiré")], default="draft", max_length=16)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="journey_plan_templates", to="activities.activity")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_journey_plan_templates", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["activity", "key", "version"]},
        ),
        migrations.CreateModel(
            name="JourneyPlanTemplateStep",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(max_length=120)),
                ("kind", models.CharField(choices=[("action", "Action"), ("document", "Document"), ("review", "Revue"), ("payment", "Paiement"), ("meeting", "Rendez-vous"), ("submission", "Soumission"), ("follow_up", "Suivi"), ("decision", "Décision"), ("other", "Autre")], default="action", max_length=24)),
                ("actor_kind", models.CharField(choices=[("beneficiary", "Bénéficiaire"), ("operator", "Porteur / opérateur")], default="beneficiary", max_length=16)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_required", models.BooleanField(default=True)),
                ("relative_due_days", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="journeys.journeyplantemplate")),
            ],
            options={"ordering": ["template", "position", "created_at", "id"]},
        ),
        migrations.CreateModel(
            name="JourneyPlanTemplateStepDependency",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("depends_on", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dependants", to="journeys.journeyplantemplatestep")),
                ("step", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dependencies", to="journeys.journeyplantemplatestep")),
            ],
        ),
        migrations.CreateModel(
            name="JourneyPlanMaterialization",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="plan_materializations", to="journeys.journey")),
                ("journey_step", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="plan_materialization", to="journeys.journeystep")),
                ("template_step", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="materializations", to="journeys.journeyplantemplatestep")),
            ],
        ),
        migrations.AddConstraint(
            model_name="journeyplantemplate",
            constraint=models.UniqueConstraint(fields=("activity", "key", "version"), name="jour_plan_version_unique"),
        ),
        migrations.AddConstraint(
            model_name="journeyplantemplate",
            constraint=models.CheckConstraint(condition=models.Q(version__gt=0), name="jour_plan_version_positive"),
        ),
        migrations.AddConstraint(
            model_name="journeyplantemplate",
            constraint=models.UniqueConstraint(condition=models.Q(status="published"), fields=("activity", "key"), name="jour_plan_one_published"),
        ),
        migrations.AddConstraint(
            model_name="journeyplantemplatestep",
            constraint=models.UniqueConstraint(fields=("template", "key"), name="jour_plan_step_key_unique"),
        ),
        migrations.AddIndex(
            model_name="journeyplantemplatestep",
            index=models.Index(fields=["template", "position"], name="jour_plan_step_pos_idx"),
        ),
        migrations.AddConstraint(
            model_name="journeyplantemplatestepdependency",
            constraint=models.UniqueConstraint(fields=("step", "depends_on"), name="jour_plan_dependency_unique"),
        ),
        migrations.AddConstraint(
            model_name="journeyplantemplatestepdependency",
            constraint=models.CheckConstraint(condition=~models.Q(step=models.F("depends_on")), name="jour_plan_dependency_not_self"),
        ),
        migrations.AddConstraint(
            model_name="journeyplanmaterialization",
            constraint=models.UniqueConstraint(fields=("journey", "template_step"), name="jour_plan_materialization_unique"),
        ),
        migrations.AddIndex(
            model_name="journeyplanmaterialization",
            index=models.Index(fields=["journey", "created_at"], name="jour_plan_mat_journey_idx"),
        ),
    ]
