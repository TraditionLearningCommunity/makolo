import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

import journeys.collaboration_models
import journeys.storage


JOURNEY_STATUS_CHOICES = [
    ("draft", "Brouillon"), ("submitted", "Soumise"), ("pending_approval", "En attente d’approbation"),
    ("approved", "Approuvée"), ("pending_payment", "En attente de paiement"), ("confirmed", "Confirmée"),
    ("in_progress", "En cours"), ("fulfilled", "Réalisée"), ("rejected", "Rejetée"),
    ("cancelled", "Annulée"), ("expired", "Expirée"),
]


class Migration(migrations.Migration):
    dependencies = [("journeys", "0002_external_beneficiary"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.AlterField(model_name="journey", name="workflow", field=models.CharField(choices=[("purchase", "Achat"), ("order_approval", "Commande avec approbation"), ("reservation", "Réservation"), ("registration", "Inscription"), ("invitation", "Invitation"), ("service", "Service")], max_length=32)),
        migrations.AlterField(model_name="journey", name="status", field=models.CharField(choices=JOURNEY_STATUS_CHOICES, default="draft", max_length=32)),
        migrations.AlterField(model_name="journeytransition", name="from_status", field=models.CharField(choices=JOURNEY_STATUS_CHOICES, max_length=32)),
        migrations.AlterField(model_name="journeytransition", name="to_status", field=models.CharField(choices=JOURNEY_STATUS_CHOICES, max_length=32)),
        migrations.AddField(model_name="journey", name="started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(name="JourneyStep", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("kind", models.CharField(choices=[("action", "Action"), ("document", "Document"), ("review", "Revue"), ("payment", "Paiement"), ("meeting", "Rendez-vous"), ("submission", "Soumission"), ("follow_up", "Suivi"), ("decision", "Décision"), ("other", "Autre")], default="action", max_length=24)),
            ("title", models.CharField(max_length=220)), ("description", models.TextField(blank=True)),
            ("status", models.CharField(choices=[("pending", "En attente"), ("ready", "Prête"), ("in_progress", "En cours"), ("blocked", "Bloquée"), ("completed", "Terminée"), ("skipped", "Ignorée"), ("cancelled", "Annulée")], default="pending", max_length=20)),
            ("position", models.PositiveIntegerField(default=0)), ("is_required", models.BooleanField(default=True)),
            ("due_at", models.DateTimeField(blank=True, null=True)), ("origin", models.CharField(choices=[("manual", "Manuelle"), ("template", "Template"), ("automation", "Automation"), ("future_ai", "IA future")], default="manual", max_length=20)),
            ("started_at", models.DateTimeField(blank=True, null=True)), ("completed_at", models.DateTimeField(blank=True, null=True)), ("skipped_at", models.DateTimeField(blank=True, null=True)), ("cancelled_at", models.DateTimeField(blank=True, null=True)),
            ("status_reason", models.CharField(blank=True, max_length=500)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_journey_steps", to=settings.AUTH_USER_MODEL)),
            ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="journeys.journey")),
            ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="journey_steps", to="activities.occurrence")),
            ("status_changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="changed_journey_steps", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["journey", "position", "created_at", "id"], "indexes": [models.Index(fields=["journey", "status"], name="jour_step_journey_status_idx"), models.Index(fields=["journey", "position"], name="jour_step_journey_pos_idx")]}),
        migrations.CreateModel(name="JourneyStepDependency", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("depends_on", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dependants", to="journeys.journeystep")), ("step", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dependencies", to="journeys.journeystep")),
        ], options={"indexes": [models.Index(fields=["depends_on", "step"], name="jour_step_dependency_rev_idx")]}),
        migrations.AddConstraint(model_name="journeystepdependency", constraint=models.UniqueConstraint(fields=("step", "depends_on"), name="jour_step_dependency_unique")),
        migrations.AddConstraint(model_name="journeystepdependency", constraint=models.CheckConstraint(condition=~Q(step=models.F("depends_on")), name="jour_step_dependency_not_self")),
        migrations.CreateModel(name="JourneyBlocker", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("category", models.CharField(choices=[("missing_document", "Document manquant"), ("eligibility", "Éligibilité"), ("external_dependency", "Dépendance externe"), ("administrative", "Administratif"), ("technical", "Technique"), ("logistics", "Logistique"), ("financial", "Financier"), ("deadline", "Échéance"), ("other", "Autre")], default="other", max_length=32)),
            ("severity", models.CharField(choices=[("low", "Faible"), ("medium", "Moyenne"), ("high", "Élevée"), ("critical", "Critique")], default="medium", max_length=16)),
            ("title", models.CharField(max_length=220)), ("description", models.TextField(blank=True)), ("status", models.CharField(choices=[("active", "Actif"), ("resolved", "Résolu"), ("waived", "Levée exceptionnelle")], default="active", max_length=16)),
            ("detected_at", models.DateTimeField(default=django.utils.timezone.now)), ("due_at", models.DateTimeField(blank=True, null=True)), ("resolved_at", models.DateTimeField(blank=True, null=True)), ("resolution_note", models.TextField(blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("detected_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="detected_journey_blockers", to=settings.AUTH_USER_MODEL)), ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blockers", to="journeys.journey")),
            ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resolved_journey_blockers", to=settings.AUTH_USER_MODEL)), ("responsible_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="responsible_journey_blockers", to=settings.AUTH_USER_MODEL)),
            ("step", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="blockers", to="journeys.journeystep")),
        ], options={"ordering": ["-detected_at", "id"], "indexes": [models.Index(fields=["journey", "status"], name="jour_block_journey_status_idx"), models.Index(fields=["step", "status"], name="jour_block_step_status_idx")]}),
        migrations.CreateModel(name="JourneyAssignment", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("responsibility", models.CharField(choices=[("lead", "Responsable principal"), ("facilitator", "Facilitateur"), ("reviewer", "Reviewer"), ("support", "Support")], max_length=20)),
            ("status", models.CharField(choices=[("active", "Active"), ("ended", "Terminée"), ("cancelled", "Annulée")], default="active", max_length=16)), ("is_primary", models.BooleanField(default=False)), ("assigned_at", models.DateTimeField(default=django.utils.timezone.now)), ("ended_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journey_assignments_created", to=settings.AUTH_USER_MODEL)), ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="journeys.journey")), ("profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journey_assignments", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["journey", "responsibility", "assigned_at", "id"], "indexes": [models.Index(fields=["journey", "status"], name="jour_assign_journey_status_idx"), models.Index(fields=["profile", "status"], name="jour_assign_profile_status_idx")]}),
        migrations.AddConstraint(model_name="journeyassignment", constraint=models.UniqueConstraint(condition=Q(responsibility="lead", is_primary=True, status="active"), fields=("journey",), name="jour_assignment_one_primary_lead")),
        migrations.AddConstraint(model_name="journeyassignment", constraint=models.UniqueConstraint(condition=Q(status="active"), fields=("journey", "profile", "responsibility"), name="jour_assignment_active_unique")),
        migrations.CreateModel(name="JourneyStepAssignment", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("responsibility", models.CharField(choices=[("lead", "Responsable principal"), ("facilitator", "Facilitateur"), ("reviewer", "Reviewer"), ("support", "Support")], max_length=20)),
            ("status", models.CharField(choices=[("active", "Active"), ("ended", "Terminée"), ("cancelled", "Annulée")], default="active", max_length=16)), ("assigned_at", models.DateTimeField(default=django.utils.timezone.now)), ("ended_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journey_step_assignments_created", to=settings.AUTH_USER_MODEL)), ("profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journey_step_assignments", to=settings.AUTH_USER_MODEL)), ("step", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="journeys.journeystep")),
        ], options={"indexes": [models.Index(fields=["step", "status"], name="jour_step_assign_status_idx")]}),
        migrations.AddConstraint(model_name="journeystepassignment", constraint=models.UniqueConstraint(condition=Q(status="active"), fields=("step", "profile", "responsibility"), name="jour_step_assignment_active_unique")),
        migrations.CreateModel(name="JourneyArtifact", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("kind", models.CharField(choices=[("cv", "CV"), ("cover_letter", "Lettre de motivation"), ("certificate", "Certificat"), ("transcript", "Relevé"), ("recommendation", "Recommandation"), ("identity_document", "Document d’identité"), ("form", "Formulaire"), ("payment_receipt", "Reçu de paiement"), ("other", "Autre")], default="other", max_length=32)),
            ("title", models.CharField(max_length=220)), ("file", models.FileField(max_length=500, storage=journeys.storage.PrivateArtifactStorage(), upload_to=journeys.collaboration_models.journey_artifact_upload_to)),
            ("status", models.CharField(choices=[("draft", "Brouillon"), ("submitted", "Soumis"), ("in_review", "En revue"), ("accepted", "Accepté"), ("rejected", "À corriger"), ("superseded", "Remplacé")], default="draft", max_length=16)),
            ("sensitivity", models.CharField(choices=[("normal", "Normale"), ("sensitive", "Sensible"), ("restricted", "Restreinte")], default="normal", max_length=16)), ("version", models.PositiveIntegerField(default=1)), ("uploaded_at", models.DateTimeField(default=django.utils.timezone.now)), ("size", models.PositiveBigIntegerField()), ("mime_type", models.CharField(max_length=180)), ("content_hash", models.CharField(max_length=64)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="artifacts", to="journeys.journey")), ("step", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="artifacts", to="journeys.journeystep")), ("supersedes", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="superseded_by", to="journeys.journeyartifact")), ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uploaded_journey_artifacts", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["journey", "kind", "title", "version", "created_at"], "indexes": [models.Index(fields=["journey", "status"], name="jour_art_journey_status_idx"), models.Index(fields=["journey", "sensitivity"], name="jour_art_journey_sens_idx")]}),
        migrations.AddConstraint(model_name="journeyartifact", constraint=models.UniqueConstraint(fields=("journey", "kind", "title", "version"), name="jour_artifact_version_unique")),
        migrations.AddConstraint(model_name="journeyartifact", constraint=models.CheckConstraint(condition=Q(version__gte=1), name="jour_artifact_version_positive")),
        migrations.CreateModel(name="JourneyArtifactReview", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("status", models.CharField(choices=[("requested", "Demandée"), ("in_progress", "En cours"), ("approved", "Approuvée"), ("changes_requested", "Modifications demandées"), ("cancelled", "Annulée")], default="requested", max_length=24)), ("comment", models.TextField(blank=True)), ("requested_at", models.DateTimeField(default=django.utils.timezone.now)), ("started_at", models.DateTimeField(blank=True, null=True)), ("decided_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("artifact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reviews", to="journeys.journeyartifact")), ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_journey_artifact_reviews", to=settings.AUTH_USER_MODEL)), ("reviewer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journey_artifact_reviews", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["-requested_at", "id"], "indexes": [models.Index(fields=["artifact", "status"], name="jour_art_review_status_idx")]}),
        migrations.CreateModel(name="JourneyNote", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("visibility", models.CharField(choices=[("beneficiary_visible", "Visible au bénéficiaire"), ("internal", "Interne")], max_length=24)), ("body", models.TextField()), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journey_notes", to=settings.AUTH_USER_MODEL)), ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notes", to="journeys.journey")), ("step", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="notes", to="journeys.journeystep")),
        ], options={"ordering": ["created_at", "id"], "indexes": [models.Index(fields=["journey", "visibility"], name="jour_note_visibility_idx")]}),
    ]
