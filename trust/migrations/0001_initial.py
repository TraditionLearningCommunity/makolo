# Generated for Makolo M4 Trust & Quality.
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models

import accounts.validators


def backfill_legacy_organization_verification(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    VerificationClaim = apps.get_model("trust", "VerificationClaim")
    for space in Organization.objects.filter(verification_status__in=["pending", "verified"]).iterator():
        status = "verified" if space.verification_status == "verified" else "under_review"
        defaults = {
            "status": status,
            "requested_by_id": space.created_by_id,
            "requested_at": space.created_at,
            "reviewed_at": space.updated_at if status == "verified" else None,
            "valid_from": space.updated_at if status == "verified" else None,
            "disclosure": "public_result",
            "source": "legacy-organization-status",
        }
        VerificationClaim.objects.get_or_create(
            subject_space_id=space.pk,
            claim_type="organization_identity",
            source="legacy-organization-status",
            defaults=defaults,
        )


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_profilefollow"),
        ("activities", "0003_activity_owner_profile"),
        ("journeys", "0003_services_core_journey_collaboration"),
        ("access", "0003_external_beneficiary"),
    ]
    operations = [
        migrations.CreateModel(
            name="VerificationClaim",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("claim_type", models.CharField(choices=[("profile_identity", "Identité du Profil"), ("organization_identity", "Identité de l’Espace"), ("contact", "Coordonnées")], max_length=40)),
                ("status", models.CharField(choices=[("requested", "Demandée"), ("under_review", "En revue"), ("verified", "Vérifiée"), ("rejected", "Rejetée"), ("expired", "Expirée"), ("revoked", "Révoquée")], default="requested", max_length=20)),
                ("requested_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("valid_from", models.DateTimeField(blank=True, null=True)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("decision_reason_code", models.SlugField(blank=True, max_length=80)),
                ("decision_note_private", models.TextField(blank=True)),
                ("disclosure", models.CharField(choices=[("private", "Privé"), ("public_result", "Résultat public")], default="public_result", max_length=20)),
                ("source", models.CharField(blank=True, default="makolo", max_length=80)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_trust_verifications", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_trust_verifications", to=settings.AUTH_USER_MODEL)),
                ("subject_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_verification_claims", to=settings.AUTH_USER_MODEL)),
                ("subject_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_verification_claims", to="organizations.organization")),
            ],
            options={"ordering": ["-requested_at", "id"]},
        ),
        migrations.CreateModel(
            name="Feedback",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("delivery", models.CharField(choices=[("not_applicable", "Non applicable"), ("yes", "Oui"), ("no", "Non")], default="not_applicable", max_length=20)),
                ("timeliness", models.CharField(choices=[("not_applicable", "Non applicable"), ("yes", "Oui"), ("no", "Non")], default="not_applicable", max_length=20)),
                ("access_experience", models.CharField(choices=[("not_applicable", "Non applicable"), ("yes", "Oui"), ("no", "Non")], default="not_applicable", max_length=20)),
                ("accuracy", models.CharField(choices=[("not_applicable", "Non applicable"), ("yes", "Oui"), ("no", "Non")], default="not_applicable", max_length=20)),
                ("overall_sentiment", models.CharField(blank=True, choices=[("positive", "Positif"), ("neutral", "Neutre"), ("negative", "Négatif")], max_length=12)),
                ("comment", models.TextField(blank=True, max_length=3000)),
                ("moderation_status", models.CharField(choices=[("visible", "Visible"), ("hidden", "Masqué")], default="visible", max_length=12)),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("withdrawn_at", models.DateTimeField(blank=True, null=True)),
                ("moderated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trust_feedback", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trust_feedback", to="journeys.journey")),
                ("moderated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="moderated_trust_feedback", to=settings.AUTH_USER_MODEL)),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_feedback", to="activities.occurrence")),
            ],
            options={"ordering": ["-submitted_at", "id"]},
        ),
        migrations.CreateModel(
            name="Report",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("category", models.CharField(choices=[("service_not_delivered", "Prestation non délivrée"), ("access_problem", "Problème d’accès"), ("misleading_information", "Information trompeuse"), ("safety_issue", "Problème de sécurité"), ("conduct_issue", "Problème de conduite"), ("other", "Autre")], max_length=32)),
                ("description", models.TextField(max_length=5000)),
                ("status", models.CharField(choices=[("open", "Ouvert"), ("triaged", "Trié"), ("investigating", "En investigation"), ("resolved", "Résolu"), ("dismissed", "Classé sans suite")], default="open", max_length=20)),
                ("triaged_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_code", models.SlugField(blank=True, max_length=80)),
                ("staff_note_private", models.TextField(blank=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("access_use", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_reports", to="access.accessuse")),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_reports", to="activities.activity")),
                ("journey", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_reports", to="journeys.journey")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_reports", to="activities.occurrence")),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trust_reports", to=settings.AUTH_USER_MODEL)),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resolved_trust_reports", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_reports", to="organizations.organization")),
                ("triaged_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="triaged_trust_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="Dispute",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("open", "Ouvert"), ("under_review", "En revue"), ("awaiting_information", "Information attendue"), ("decided", "Décidé"), ("closed", "Clos")], default="open", max_length=24)),
                ("decision_code", models.SlugField(blank=True, max_length=80)),
                ("decision_summary", models.TextField(blank=True, max_length=3000)),
                ("decision_note_private", models.TextField(blank=True)),
                ("remedy_code", models.CharField(choices=[("no_action", "Aucune action"), ("operator_action_required", "Action opérateur requise"), ("access_reissue_requested", "Réémission d’accès demandée"), ("correction_required", "Correction requise"), ("refund_requested", "Remboursement demandé"), ("other", "Autre")], default="no_action", max_length=32)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("claimant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trust_disputes_claimed", to=settings.AUTH_USER_MODEL)),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="decided_trust_disputes", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_disputes", to="journeys.journey")),
                ("report", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="dispute", to="trust.report")),
                ("respondent_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_disputes_received", to=settings.AUTH_USER_MODEL)),
                ("respondent_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_disputes", to="organizations.organization")),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="TrustEvidence",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("file", models.FileField(upload_to="trust/private-evidence/%Y/%m/", validators=[accounts.validators.validate_verification_document])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("report", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="evidence", to="trust.report")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trust_evidence_uploaded", to=settings.AUTH_USER_MODEL)),
                ("verification_claim", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="evidence", to="trust.verificationclaim")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="Proof",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("proof_type", models.CharField(choices=[("journey_completed", "Journey accomplie"), ("participation_confirmed", "Participation confirmée"), ("access_used", "Accès utilisé"), ("service_completed", "Service complété")], max_length=32)),
                ("status", models.CharField(choices=[("active", "Active"), ("revoked", "Révoquée")], default="active", max_length=12)),
                ("is_public", models.BooleanField(default=False)),
                ("issued_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoke_reason", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_trust_proofs", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trust_proofs", to="journeys.journey")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trust_proofs", to="activities.occurrence")),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="revoked_trust_proofs", to=settings.AUTH_USER_MODEL)),
                ("subject_profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trust_proofs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-issued_at", "id"]},
        ),
        migrations.AddConstraint(model_name="verificationclaim", constraint=models.CheckConstraint(condition=models.Q(("subject_profile__isnull", False), ("subject_space__isnull", True), _connector="AND") | models.Q(("subject_profile__isnull", True), ("subject_space__isnull", False), _connector="AND"), name="trust_verify_exactly_one_subject")),
        migrations.AddConstraint(model_name="verificationclaim", constraint=models.CheckConstraint(condition=models.Q(("valid_until__isnull", True)) | models.Q(("valid_from__isnull", True)) | models.Q(("valid_until__gt", models.F("valid_from"))), name="trust_verify_valid_window")),
        migrations.AddConstraint(model_name="feedback", constraint=models.UniqueConstraint(fields=("journey", "author"), name="trust_feedback_journey_author_unique")),
        migrations.AddConstraint(model_name="dispute", constraint=models.CheckConstraint(condition=models.Q(("respondent_profile__isnull", False), ("respondent_space__isnull", True), _connector="AND") | models.Q(("respondent_profile__isnull", True), ("respondent_space__isnull", False), _connector="AND"), name="trust_dispute_one_respondent")),
        migrations.AddConstraint(model_name="trustevidence", constraint=models.CheckConstraint(condition=models.Q(("verification_claim__isnull", False), ("report__isnull", True), _connector="AND") | models.Q(("verification_claim__isnull", True), ("report__isnull", False), _connector="AND"), name="trust_evidence_one_parent")),
        migrations.AddConstraint(model_name="proof", constraint=models.UniqueConstraint(fields=("subject_profile", "journey", "proof_type"), name="trust_proof_fact_unique")),
        migrations.AddIndex(model_name="verificationclaim", index=models.Index(fields=["status", "requested_at"], name="trust_verify_queue_idx")),
        migrations.AddIndex(model_name="verificationclaim", index=models.Index(fields=["subject_space", "claim_type", "status"], name="trust_verify_space_idx")),
        migrations.AddIndex(model_name="verificationclaim", index=models.Index(fields=["subject_profile", "claim_type", "status"], name="trust_verify_profile_idx")),
        migrations.AddIndex(model_name="verificationclaim", index=models.Index(fields=["valid_until"], name="trust_verify_valid_until_idx")),
        migrations.AddIndex(model_name="feedback", index=models.Index(fields=["author", "submitted_at"], name="trust_feedback_author_idx")),
        migrations.AddIndex(model_name="feedback", index=models.Index(fields=["overall_sentiment", "submitted_at"], name="trust_feedback_sentiment_idx")),
        migrations.AddIndex(model_name="report", index=models.Index(fields=["status", "created_at"], name="trust_report_queue_idx")),
        migrations.AddIndex(model_name="report", index=models.Index(fields=["space", "status"], name="trust_report_space_idx")),
        migrations.AddIndex(model_name="report", index=models.Index(fields=["reporter", "created_at"], name="trust_report_reporter_idx")),
        migrations.AddIndex(model_name="dispute", index=models.Index(fields=["status", "created_at"], name="trust_dispute_queue_idx")),
        migrations.AddIndex(model_name="proof", index=models.Index(fields=["subject_profile", "status"], name="trust_proof_owner_idx")),
        migrations.AddIndex(model_name="proof", index=models.Index(fields=["public_id", "status"], name="trust_proof_public_idx")),
        migrations.RunPython(backfill_legacy_organization_verification, migrations.RunPython.noop),
    ]
