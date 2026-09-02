import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.validators import validate_verification_document


class VerificationClaimType(models.TextChoices):
    PROFILE_IDENTITY = "profile_identity", "Identité du Profil"
    ORGANIZATION_IDENTITY = "organization_identity", "Identité de l’Espace"
    CONTACT = "contact", "Coordonnées"


class VerificationStatus(models.TextChoices):
    REQUESTED = "requested", "Demandée"
    UNDER_REVIEW = "under_review", "En revue"
    VERIFIED = "verified", "Vérifiée"
    REJECTED = "rejected", "Rejetée"
    EXPIRED = "expired", "Expirée"
    REVOKED = "revoked", "Révoquée"


class VerificationDisclosure(models.TextChoices):
    PRIVATE = "private", "Privé"
    PUBLIC_RESULT = "public_result", "Résultat public"


class VerificationClaim(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="trust_verification_claims",
        null=True,
        blank=True,
    )
    subject_space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="trust_verification_claims",
        null=True,
        blank=True,
    )
    claim_type = models.CharField(max_length=40, choices=VerificationClaimType.choices)
    status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.REQUESTED)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="requested_trust_verifications",
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_trust_verifications",
        null=True,
        blank=True,
    )
    requested_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    decision_reason_code = models.SlugField(max_length=80, blank=True)
    decision_note_private = models.TextField(blank=True)
    disclosure = models.CharField(
        max_length=20,
        choices=VerificationDisclosure.choices,
        default=VerificationDisclosure.PUBLIC_RESULT,
    )
    source = models.CharField(max_length=80, default="makolo", blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at", "id"]
        indexes = [
            models.Index(fields=["status", "requested_at"], name="trust_verify_queue_idx"),
            models.Index(fields=["subject_space", "claim_type", "status"], name="trust_verify_space_idx"),
            models.Index(fields=["subject_profile", "claim_type", "status"], name="trust_verify_profile_idx"),
            models.Index(fields=["valid_until"], name="trust_verify_valid_until_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(Q(subject_profile__isnull=False, subject_space__isnull=True) | Q(subject_profile__isnull=True, subject_space__isnull=False)),
                name="trust_verify_exactly_one_subject",
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_from__isnull=True) | Q(valid_until__gt=models.F("valid_from")),
                name="trust_verify_valid_window",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if bool(self.subject_profile_id) == bool(self.subject_space_id):
            errors["subject_profile"] = "Une vérification doit viser exactement un Profil ou un Espace."
        if self.reviewed_by_id and self.requested_by_id and self.reviewed_by_id == self.requested_by_id:
            errors["reviewed_by"] = "Une demande ne peut pas être auto-vérifiée par son demandeur."
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            errors["valid_until"] = "La fin de validité doit être postérieure au début."
        if errors:
            raise ValidationError(errors)

    @property
    def is_currently_verified(self):
        if self.status != VerificationStatus.VERIFIED:
            return False
        now = timezone.now()
        return (self.valid_from is None or self.valid_from <= now) and (self.valid_until is None or self.valid_until > now)


class FeedbackAnswer(models.TextChoices):
    NOT_APPLICABLE = "not_applicable", "Non applicable"
    YES = "yes", "Oui"
    NO = "no", "Non"


class FeedbackSentiment(models.TextChoices):
    POSITIVE = "positive", "Positif"
    NEUTRAL = "neutral", "Neutre"
    NEGATIVE = "negative", "Négatif"


class FeedbackModerationStatus(models.TextChoices):
    VISIBLE = "visible", "Visible"
    HIDDEN = "hidden", "Masqué"


class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey("journeys.Journey", on_delete=models.PROTECT, related_name="trust_feedback")
    occurrence = models.ForeignKey("activities.Occurrence", on_delete=models.PROTECT, related_name="trust_feedback", null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trust_feedback")
    delivery = models.CharField(max_length=20, choices=FeedbackAnswer.choices, default=FeedbackAnswer.NOT_APPLICABLE)
    timeliness = models.CharField(max_length=20, choices=FeedbackAnswer.choices, default=FeedbackAnswer.NOT_APPLICABLE)
    access_experience = models.CharField(max_length=20, choices=FeedbackAnswer.choices, default=FeedbackAnswer.NOT_APPLICABLE)
    accuracy = models.CharField(max_length=20, choices=FeedbackAnswer.choices, default=FeedbackAnswer.NOT_APPLICABLE)
    overall_sentiment = models.CharField(max_length=12, choices=FeedbackSentiment.choices, blank=True)
    comment = models.TextField(blank=True, max_length=3000)
    moderation_status = models.CharField(max_length=12, choices=FeedbackModerationStatus.choices, default=FeedbackModerationStatus.VISIBLE)
    submitted_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="moderated_trust_feedback", null=True, blank=True)
    moderated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at", "id"]
        constraints = [models.UniqueConstraint(fields=["journey", "author"], name="trust_feedback_journey_author_unique")]
        indexes = [
            models.Index(fields=["author", "submitted_at"], name="trust_feedback_author_idx"),
            models.Index(fields=["overall_sentiment", "submitted_at"], name="trust_feedback_sentiment_idx"),
        ]

    def clean(self):
        super().clean()
        if self.journey_id and self.occurrence_id and self.journey.occurrence_id and self.journey.occurrence_id != self.occurrence_id:
            raise ValidationError({"occurrence": "L’Occurrence du feedback doit correspondre à la Journey."})


class ReportCategory(models.TextChoices):
    SERVICE_NOT_DELIVERED = "service_not_delivered", "Prestation non délivrée"
    ACCESS_PROBLEM = "access_problem", "Problème d’accès"
    MISLEADING_INFORMATION = "misleading_information", "Information trompeuse"
    SAFETY_ISSUE = "safety_issue", "Problème de sécurité"
    CONDUCT_ISSUE = "conduct_issue", "Problème de conduite"
    OTHER = "other", "Autre"


class ReportStatus(models.TextChoices):
    OPEN = "open", "Ouvert"
    TRIAGED = "triaged", "Trié"
    INVESTIGATING = "investigating", "En investigation"
    RESOLVED = "resolved", "Résolu"
    DISMISSED = "dismissed", "Classé sans suite"


class Report(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trust_reports")
    category = models.CharField(max_length=32, choices=ReportCategory.choices)
    description = models.TextField(max_length=5000)
    journey = models.ForeignKey("journeys.Journey", on_delete=models.PROTECT, related_name="trust_reports", null=True, blank=True)
    activity = models.ForeignKey("activities.Activity", on_delete=models.PROTECT, related_name="trust_reports", null=True, blank=True)
    occurrence = models.ForeignKey("activities.Occurrence", on_delete=models.PROTECT, related_name="trust_reports", null=True, blank=True)
    access_use = models.ForeignKey("access.AccessUse", on_delete=models.PROTECT, related_name="trust_reports", null=True, blank=True)
    space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="trust_reports", null=True, blank=True)
    status = models.CharField(max_length=20, choices=ReportStatus.choices, default=ReportStatus.OPEN)
    triaged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="triaged_trust_reports", null=True, blank=True)
    triaged_at = models.DateTimeField(null=True, blank=True)
    resolution_code = models.SlugField(max_length=80, blank=True)
    staff_note_private = models.TextField(blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="resolved_trust_reports", null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="trust_report_queue_idx"),
            models.Index(fields=["space", "status"], name="trust_report_space_idx"),
            models.Index(fields=["reporter", "created_at"], name="trust_report_reporter_idx"),
        ]

    def clean(self):
        super().clean()
        if not any([self.journey_id, self.activity_id, self.occurrence_id, self.access_use_id, self.space_id]):
            raise ValidationError("Un signalement doit être rattaché à un contexte Makolo explicite.")
        if self.journey_id:
            if self.activity_id and self.journey.activity_id != self.activity_id:
                raise ValidationError({"activity": "L’Activity doit correspondre à la Journey signalée."})
            if self.occurrence_id and self.journey.occurrence_id and self.journey.occurrence_id != self.occurrence_id:
                raise ValidationError({"occurrence": "L’Occurrence doit correspondre à la Journey signalée."})


class DisputeStatus(models.TextChoices):
    OPEN = "open", "Ouvert"
    UNDER_REVIEW = "under_review", "En revue"
    AWAITING_INFORMATION = "awaiting_information", "Information attendue"
    DECIDED = "decided", "Décidé"
    CLOSED = "closed", "Clos"


class RemedyCode(models.TextChoices):
    NONE = "no_action", "Aucune action"
    OPERATOR_ACTION_REQUIRED = "operator_action_required", "Action opérateur requise"
    ACCESS_REISSUE_REQUESTED = "access_reissue_requested", "Réémission d’accès demandée"
    CORRECTION_REQUIRED = "correction_required", "Correction requise"
    REFUND_REQUESTED = "refund_requested", "Remboursement demandé"
    OTHER = "other", "Autre"


class Dispute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.OneToOneField(Report, on_delete=models.PROTECT, related_name="dispute", null=True, blank=True)
    journey = models.ForeignKey("journeys.Journey", on_delete=models.PROTECT, related_name="trust_disputes", null=True, blank=True)
    claimant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trust_disputes_claimed")
    respondent_profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trust_disputes_received", null=True, blank=True)
    respondent_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="trust_disputes", null=True, blank=True)
    status = models.CharField(max_length=24, choices=DisputeStatus.choices, default=DisputeStatus.OPEN)
    decision_code = models.SlugField(max_length=80, blank=True)
    decision_summary = models.TextField(blank=True, max_length=3000)
    decision_note_private = models.TextField(blank=True)
    remedy_code = models.CharField(max_length=32, choices=RemedyCode.choices, default=RemedyCode.NONE)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="decided_trust_disputes", null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [models.Index(fields=["status", "created_at"], name="trust_dispute_queue_idx")]
        constraints = [
            models.CheckConstraint(
                condition=(Q(respondent_profile__isnull=False, respondent_space__isnull=True) | Q(respondent_profile__isnull=True, respondent_space__isnull=False)),
                name="trust_dispute_one_respondent",
            )
        ]

    def clean(self):
        super().clean()
        if bool(self.respondent_profile_id) == bool(self.respondent_space_id):
            raise ValidationError("Un litige doit avoir exactement une partie répondante.")
        if self.report_id and self.journey_id and self.report.journey_id and self.report.journey_id != self.journey_id:
            raise ValidationError({"journey": "La Journey du litige doit correspondre au signalement."})


class TrustEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    verification_claim = models.ForeignKey(VerificationClaim, on_delete=models.CASCADE, related_name="evidence", null=True, blank=True)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="evidence", null=True, blank=True)
    file = models.FileField(upload_to="trust/private-evidence/%Y/%m/", validators=[validate_verification_document])
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trust_evidence_uploaded")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(verification_claim__isnull=False, report__isnull=True) | Q(verification_claim__isnull=True, report__isnull=False)),
                name="trust_evidence_one_parent",
            )
        ]


class ProofType(models.TextChoices):
    JOURNEY_COMPLETED = "journey_completed", "Journey accomplie"
    PARTICIPATION_CONFIRMED = "participation_confirmed", "Participation confirmée"
    ACCESS_USED = "access_used", "Accès utilisé"
    SERVICE_COMPLETED = "service_completed", "Service complété"


class ProofStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REVOKED = "revoked", "Révoquée"


class Proof(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    subject_profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trust_proofs")
    journey = models.ForeignKey("journeys.Journey", on_delete=models.PROTECT, related_name="trust_proofs")
    occurrence = models.ForeignKey("activities.Occurrence", on_delete=models.PROTECT, related_name="trust_proofs", null=True, blank=True)
    proof_type = models.CharField(max_length=32, choices=ProofType.choices)
    status = models.CharField(max_length=12, choices=ProofStatus.choices, default=ProofStatus.ACTIVE)
    is_public = models.BooleanField(default=False)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="issued_trust_proofs", null=True, blank=True)
    issued_at = models.DateTimeField(default=timezone.now)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="revoked_trust_proofs", null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at", "id"]
        constraints = [models.UniqueConstraint(fields=["subject_profile", "journey", "proof_type"], name="trust_proof_fact_unique")]
        indexes = [
            models.Index(fields=["subject_profile", "status"], name="trust_proof_owner_idx"),
            models.Index(fields=["public_id", "status"], name="trust_proof_public_idx"),
        ]

    def clean(self):
        super().clean()
        if self.journey_id and self.subject_profile_id != self.journey.beneficiary_id:
            raise ValidationError({"subject_profile": "Le détenteur de la preuve doit être le bénéficiaire Profile de la Journey."})
        if self.occurrence_id and self.journey.occurrence_id and self.journey.occurrence_id != self.occurrence_id:
            raise ValidationError({"occurrence": "L’Occurrence doit correspondre à la Journey."})
