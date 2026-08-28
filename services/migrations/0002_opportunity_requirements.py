import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("opportunities", "0001_initial"),
        ("services", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="servicejourneycontext",
            name="opportunity",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="service_contexts", to="opportunities.opportunity"),
        ),
        migrations.AddField(
            model_name="servicejourneycontext",
            name="opportunity_revision",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="service_contexts", to="opportunities.opportunityrevision"),
        ),
        migrations.AddConstraint(
            model_name="servicejourneycontext",
            constraint=models.CheckConstraint(condition=(Q(opportunity__isnull=True, opportunity_revision__isnull=True) | Q(opportunity__isnull=False, opportunity_revision__isnull=False)), name="services_context_opp_pair"),
        ),
        migrations.CreateModel(
            name="ServiceRequirementAssessment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("unassessed", "Non évalué"), ("satisfied", "Satisfait"), ("action_required", "Action requise"), ("needs_review", "Revue requise"), ("not_applicable", "Non applicable"), ("not_eligible", "Non éligible")], default="unassessed", max_length=20)),
                ("note", models.TextField(blank=True)),
                ("assessed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assessed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="service_requirement_assessments", to=settings.AUTH_USER_MODEL)),
                ("context", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirement_assessments", to="services.servicejourneycontext")),
                ("requirement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="service_assessments", to="opportunities.opportunityrequirement")),
            ],
            options={"ordering": ["context", "requirement__position", "created_at", "id"]},
        ),
        migrations.AddConstraint(model_name="servicerequirementassessment", constraint=models.UniqueConstraint(fields=("context", "requirement"), name="services_req_assessment_unique")),
        migrations.AddIndex(model_name="servicerequirementassessment", index=models.Index(fields=["context", "status"], name="services_req_assess_status_idx")),
        migrations.AddIndex(model_name="servicerequirementassessment", index=models.Index(fields=["requirement", "status"], name="services_req_status_idx")),
        migrations.CreateModel(
            name="ServiceRequirementEvidence",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("submitted", "Soumise"), ("accepted", "Acceptée"), ("rejected", "Rejetée")], default="submitted", max_length=16)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("artifact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="requirement_evidence", to="journeys.journeyartifact")),
                ("assessment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="evidence", to="services.servicerequirementassessment")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_service_requirement_evidence", to=settings.AUTH_USER_MODEL)),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_service_requirement_evidence", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(model_name="servicerequirementevidence", constraint=models.UniqueConstraint(fields=("assessment", "artifact"), name="services_req_evidence_unique")),
        migrations.AddIndex(model_name="servicerequirementevidence", index=models.Index(fields=["assessment", "status"], name="services_req_evid_status_idx")),
        migrations.CreateModel(
            name="ServiceOpportunityRevisionAdoption",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("adopted_at", models.DateTimeField(auto_now_add=True)),
                ("adopted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="service_opportunity_revision_adoptions", to=settings.AUTH_USER_MODEL)),
                ("context", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="opportunity_revision_adoptions", to="services.servicejourneycontext")),
                ("previous_revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="service_adoptions_from", to="opportunities.opportunityrevision")),
                ("revision", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="service_adoptions_to", to="opportunities.opportunityrevision")),
            ],
            options={"ordering": ["context", "adopted_at", "id"]},
        ),
        migrations.AddConstraint(model_name="serviceopportunityrevisionadoption", constraint=models.UniqueConstraint(fields=("context", "revision"), name="services_opp_adoption_unique")),
        migrations.AddIndex(model_name="serviceopportunityrevisionadoption", index=models.Index(fields=["context", "adopted_at"], name="services_opp_adopt_ctx_idx")),
        migrations.CreateModel(
            name="ServiceRequirementStepLink",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assessment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="step_links", to="services.servicerequirementassessment")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_service_requirement_step_links", to=settings.AUTH_USER_MODEL)),
                ("journey_step", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="requirement_links", to="journeys.journeystep")),
            ],
        ),
        migrations.AddConstraint(model_name="servicerequirementsteplink", constraint=models.UniqueConstraint(fields=("assessment", "journey_step"), name="services_req_step_link_unique")),
        migrations.AddIndex(model_name="servicerequirementsteplink", index=models.Index(fields=["assessment"], name="services_req_step_link_idx")),
    ]
