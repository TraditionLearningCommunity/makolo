import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("activities", "0003_activity_owner_profile"),
        ("journeys", "0003_services_core_journey_collaboration"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceDetails",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("service_kind", models.CharField(choices=[("application_support", "Accompagnement de candidature"), ("career_support", "Accompagnement carrière"), ("education_guidance", "Orientation éducative"), ("document_support", "Accompagnement documentaire"), ("administrative_support", "Accompagnement administratif"), ("interview_preparation", "Préparation d’entretien"), ("orientation", "Orientation"), ("other", "Autre")], max_length=32)),
                ("opportunity_policy", models.CharField(choices=[("required", "Opportunity requise"), ("optional", "Opportunity facultative"), ("none", "Sans Opportunity")], default="none", max_length=16)),
                ("intake_policy", models.CharField(choices=[("auto_confirm", "Confirmation automatique"), ("review_required", "Revue requise")], default="auto_confirm", max_length=24)),
                ("allows_external_beneficiary", models.BooleanField(default=False)),
                ("completion_policy", models.CharField(choices=[("required_steps", "Étapes obligatoires satisfaites")], default="required_steps", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="service_details", to="activities.activity")),
            ],
            options={"ordering": ["activity__title", "id"]},
        ),
        migrations.CreateModel(
            name="ServicePlanTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(max_length=120)),
                ("version", models.PositiveIntegerField(default=1)),
                ("name", models.CharField(max_length=220)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publié"), ("retired", "Retiré")], default="draft", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_service_plan_templates", to=settings.AUTH_USER_MODEL)),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="plan_templates", to="services.servicedetails")),
            ],
            options={"ordering": ["service", "key", "version"]},
        ),
        migrations.AddConstraint(model_name="serviceplantemplate", constraint=models.UniqueConstraint(fields=("service", "key", "version"), name="services_plan_version_unique")),
        migrations.AddConstraint(model_name="serviceplantemplate", constraint=models.CheckConstraint(condition=Q(version__gte=1), name="services_plan_version_positive")),
        migrations.CreateModel(
            name="ServicePlanTemplateStep",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("action", "Action"), ("document", "Document"), ("review", "Revue"), ("payment", "Paiement"), ("meeting", "Rendez-vous"), ("submission", "Soumission"), ("follow_up", "Suivi"), ("decision", "Décision"), ("other", "Autre")], default="action", max_length=24)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_required", models.BooleanField(default=True)),
                ("relative_due_days", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="services.serviceplantemplate")),
            ],
            options={"ordering": ["template", "position", "created_at", "id"], "indexes": [models.Index(fields=["template", "position"], name="services_tpl_step_pos_idx")]},
        ),
        migrations.CreateModel(
            name="ServicePlanTemplateStepDependency",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("depends_on", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dependants", to="services.serviceplantemplatestep")),
                ("step", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dependencies", to="services.serviceplantemplatestep")),
            ],
        ),
        migrations.AddConstraint(model_name="serviceplantemplatestepdependency", constraint=models.UniqueConstraint(fields=("step", "depends_on"), name="services_tpl_dependency_unique")),
        migrations.AddConstraint(model_name="serviceplantemplatestepdependency", constraint=models.CheckConstraint(condition=~Q(step=models.F("depends_on")), name="services_tpl_dependency_not_self")),
        migrations.CreateModel(
            name="ServiceJourneyContext",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("objective", models.TextField(blank=True)),
                ("plan_materialized_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("journey", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="service_context", to="journeys.journey")),
                ("service_plan_template", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="journey_contexts", to="services.serviceplantemplate")),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="ServicePlanMaterialization",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("context", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="materialized_steps", to="services.servicejourneycontext")),
                ("journey_step", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="journeys.journeystep")),
                ("template_step", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="materializations", to="services.serviceplantemplatestep")),
            ],
        ),
        migrations.AddConstraint(model_name="serviceplanmaterialization", constraint=models.UniqueConstraint(fields=("context", "template_step"), name="services_materialization_step_unique")),
        migrations.CreateModel(
            name="ServiceIntakeQuestion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(max_length=120)),
                ("prompt", models.CharField(max_length=500)),
                ("question_type", models.CharField(choices=[("short_text", "Texte court"), ("long_text", "Texte long"), ("boolean", "Oui / non"), ("date", "Date"), ("single_choice", "Choix unique"), ("multiple_choice", "Choix multiples")], max_length=24)),
                ("is_required", models.BooleanField(default=True)),
                ("options", models.JSONField(blank=True, default=list)),
                ("position", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("service", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="intake_questions", to="services.servicedetails")),
                ("template", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="intake_questions", to="services.serviceplantemplate")),
            ],
            options={"ordering": ["position", "created_at", "id"]},
        ),
        migrations.AddConstraint(model_name="serviceintakequestion", constraint=models.CheckConstraint(condition=(Q(service__isnull=False, template__isnull=True) | Q(service__isnull=True, template__isnull=False)), name="services_intake_question_one_target")),
        migrations.AddConstraint(model_name="serviceintakequestion", constraint=models.UniqueConstraint(condition=Q(service__isnull=False), fields=("service", "key"), name="services_intake_service_key_unique")),
        migrations.AddConstraint(model_name="serviceintakequestion", constraint=models.UniqueConstraint(condition=Q(template__isnull=False), fields=("template", "key"), name="services_intake_template_key_unique")),
        migrations.CreateModel(
            name="ServiceIntakeAnswer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("value", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("answered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="service_intake_answers", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_intake_answers", to="journeys.journey")),
                ("question", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="answers", to="services.serviceintakequestion")),
            ],
            options={"indexes": [models.Index(fields=["journey", "created_at"], name="services_intake_answer_idx")]},
        ),
        migrations.AddConstraint(model_name="serviceintakeanswer", constraint=models.UniqueConstraint(fields=("journey", "question"), name="services_intake_answer_unique")),
    ]
