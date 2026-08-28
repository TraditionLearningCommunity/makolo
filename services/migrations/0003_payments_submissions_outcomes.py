import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payments", "0006_backfill_payment_obligations"),
        ("services", "0002_opportunity_requirements"),
    ]

    operations = [
        migrations.AlterField(
            model_name="servicedetails",
            name="completion_policy",
            field=models.CharField(
                choices=[
                    ("required_steps", "Étapes obligatoires satisfaites"),
                    ("required_steps_and_submission", "Étapes obligatoires et soumission externe"),
                ],
                default="required_steps",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="servicejourneycontext",
            name="current_outcome",
            field=models.CharField(
                choices=[
                    ("not_submitted", "Non soumis"),
                    ("submitted", "Soumis"),
                    ("acknowledged", "Réception accusée"),
                    ("under_review", "En revue"),
                    ("action_required", "Action requise"),
                    ("interview", "Entretien"),
                    ("successful", "Succès"),
                    ("unsuccessful", "Échec externe"),
                    ("withdrawn", "Retiré"),
                    ("unknown", "Inconnu"),
                ],
                default="not_submitted",
                max_length=24,
            ),
        ),
        migrations.CreateModel(
            name="ServiceRequirementPaymentObligation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assessment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_obligation_links", to="services.servicerequirementassessment")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_requirement_payment_links", to=settings.AUTH_USER_MODEL)),
                ("obligation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="service_requirement_links", to="payments.paymentobligation")),
            ],
        ),
        migrations.AddConstraint(
            model_name="servicerequirementpaymentobligation",
            constraint=models.UniqueConstraint(fields=("assessment", "obligation"), name="services_req_payment_obligation_unique"),
        ),
        migrations.AddIndex(
            model_name="servicerequirementpaymentobligation",
            index=models.Index(fields=["assessment"], name="services_req_payobl_assess_idx"),
        ),
        migrations.CreateModel(
            name="ServiceSubmission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("attempt", models.PositiveIntegerField()),
                ("mode", models.CharField(choices=[("external_web", "Portail web externe"), ("email", "E-mail"), ("in_person", "En personne"), ("makolo_integrated", "Intégration Makolo"), ("other", "Autre")], max_length=24)),
                ("status", models.CharField(choices=[("prepared", "Préparée"), ("submitted", "Soumise"), ("acknowledged", "Réception accusée"), ("failed", "Échouée"), ("withdrawn", "Retirée")], default="prepared", max_length=16)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("external_reference", models.CharField(blank=True, max_length=240)),
                ("failure_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("context", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submissions", to="services.servicejourneycontext")),
                ("receipt_artifact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="service_submission_receipts", to="journeys.journeyartifact")),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="service_submissions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["context", "attempt", "created_at", "id"]},
        ),
        migrations.AddConstraint(model_name="servicesubmission", constraint=models.UniqueConstraint(fields=("context", "attempt"), name="services_submission_attempt_unique")),
        migrations.AddConstraint(model_name="servicesubmission", constraint=models.CheckConstraint(condition=Q(attempt__gte=1), name="services_submission_attempt_positive")),
        migrations.AddIndex(model_name="servicesubmission", index=models.Index(fields=["context", "status"], name="services_submission_status_idx")),
        migrations.AddIndex(model_name="servicesubmission", index=models.Index(fields=["context", "attempt"], name="services_sub_attempt_idx")),
        migrations.CreateModel(
            name="ServiceOutcomeEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(choices=[("submitted", "Soumis"), ("acknowledged", "Réception accusée"), ("under_review", "En revue"), ("action_required", "Action requise"), ("interview", "Entretien"), ("successful", "Succès"), ("unsuccessful", "Échec externe"), ("withdrawn", "Retiré"), ("other", "Autre")], max_length=24)),
                ("occurred_at", models.DateTimeField()),
                ("note", models.TextField(blank=True)),
                ("external_reference", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("context", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="outcome_events", to="services.servicejourneycontext")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recorded_service_outcomes", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["context", "occurred_at", "created_at", "id"]},
        ),
        migrations.AddIndex(model_name="serviceoutcomeevent", index=models.Index(fields=["context", "occurred_at"], name="services_outcome_time_idx")),
    ]
