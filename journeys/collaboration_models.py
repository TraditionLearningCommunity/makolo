import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .storage import private_artifact_storage


class JourneyStepKind(models.TextChoices):
    ACTION = "action", "Action"
    DOCUMENT = "document", "Document"
    REVIEW = "review", "Revue"
    PAYMENT = "payment", "Paiement"
    MEETING = "meeting", "Rendez-vous"
    SUBMISSION = "submission", "Soumission"
    FOLLOW_UP = "follow_up", "Suivi"
    DECISION = "decision", "Décision"
    OTHER = "other", "Autre"


class JourneyStepStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    READY = "ready", "Prête"
    IN_PROGRESS = "in_progress", "En cours"
    BLOCKED = "blocked", "Bloquée"
    COMPLETED = "completed", "Terminée"
    SKIPPED = "skipped", "Ignorée"
    CANCELLED = "cancelled", "Annulée"


TERMINAL_STEP_STATUSES = {
    JourneyStepStatus.COMPLETED,
    JourneyStepStatus.SKIPPED,
    JourneyStepStatus.CANCELLED,
}


class JourneyStepOrigin(models.TextChoices):
    MANUAL = "manual", "Manuelle"
    TEMPLATE = "template", "Template"
    AUTOMATION = "automation", "Automation"
    FUTURE_AI = "future_ai", "IA future"


class JourneyStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey("journeys.Journey", on_delete=models.CASCADE, related_name="steps")
    kind = models.CharField(max_length=24, choices=JourneyStepKind.choices, default=JourneyStepKind.ACTION)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=JourneyStepStatus.choices, default=JourneyStepStatus.PENDING)
    position = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    due_at = models.DateTimeField(null=True, blank=True)
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.PROTECT,
        related_name="journey_steps",
        null=True,
        blank=True,
    )
    origin = models.CharField(max_length=20, choices=JourneyStepOrigin.choices, default=JourneyStepOrigin.MANUAL)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    skipped_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_journey_steps",
        null=True,
        blank=True,
    )
    status_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="changed_journey_steps",
        null=True,
        blank=True,
    )
    status_reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["journey", "position", "created_at", "id"]
        indexes = [
            models.Index(fields=["journey", "status"], name="jour_step_journey_status_idx"),
            models.Index(fields=["journey", "position"], name="jour_step_journey_pos_idx"),
        ]

    def clean(self):
        super().clean()
        if self.occurrence_id and self.journey_id:
            if self.occurrence.activity_id != self.journey.activity_id:
                raise ValidationError({"occurrence": "L’Occurrence doit appartenir à l’Activity de la Journey."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = JourneyStep.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez les services de transition JourneyStep."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    @property
    def is_terminal(self):
        return self.status in TERMINAL_STEP_STATUSES

    @property
    def is_overdue(self):
        return bool(self.due_at and self.due_at < timezone.now() and not self.is_terminal)

    def __str__(self):
        return f"{self.journey_id} — {self.title}"


class JourneyStepDependency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step = models.ForeignKey(JourneyStep, on_delete=models.CASCADE, related_name="dependencies")
    depends_on = models.ForeignKey(JourneyStep, on_delete=models.CASCADE, related_name="dependants")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["step", "depends_on"], name="jour_step_dependency_unique"),
            models.CheckConstraint(condition=~Q(step=models.F("depends_on")), name="jour_step_dependency_not_self"),
        ]
        indexes = [models.Index(fields=["depends_on", "step"], name="jour_step_dependency_rev_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.step_id and self.depends_on_id:
            if self.step_id == self.depends_on_id:
                errors["depends_on"] = "Une étape ne peut pas dépendre d’elle-même."
            elif self.step.journey_id != self.depends_on.journey_id:
                errors["depends_on"] = "Les deux étapes doivent appartenir à la même Journey."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class JourneyBlockerCategory(models.TextChoices):
    MISSING_DOCUMENT = "missing_document", "Document manquant"
    ELIGIBILITY = "eligibility", "Éligibilité"
    EXTERNAL_DEPENDENCY = "external_dependency", "Dépendance externe"
    ADMINISTRATIVE = "administrative", "Administratif"
    TECHNICAL = "technical", "Technique"
    LOGISTICS = "logistics", "Logistique"
    FINANCIAL = "financial", "Financier"
    DEADLINE = "deadline", "Échéance"
    OTHER = "other", "Autre"


class JourneyBlockerSeverity(models.TextChoices):
    LOW = "low", "Faible"
    MEDIUM = "medium", "Moyenne"
    HIGH = "high", "Élevée"
    CRITICAL = "critical", "Critique"


class JourneyBlockerStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    RESOLVED = "resolved", "Résolu"
    WAIVED = "waived", "Levée exceptionnelle"


class JourneyBlocker(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey("journeys.Journey", on_delete=models.CASCADE, related_name="blockers")
    step = models.ForeignKey(JourneyStep, on_delete=models.PROTECT, related_name="blockers", null=True, blank=True)
    category = models.CharField(max_length=32, choices=JourneyBlockerCategory.choices, default=JourneyBlockerCategory.OTHER)
    severity = models.CharField(max_length=16, choices=JourneyBlockerSeverity.choices, default=JourneyBlockerSeverity.MEDIUM)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=JourneyBlockerStatus.choices, default=JourneyBlockerStatus.ACTIVE)
    responsible_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="responsible_journey_blockers",
        null=True,
        blank=True,
    )
    detected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="detected_journey_blockers",
        null=True,
        blank=True,
    )
    detected_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="resolved_journey_blockers",
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-detected_at", "id"]
        indexes = [
            models.Index(fields=["journey", "status"], name="jour_block_journey_status_idx"),
            models.Index(fields=["step", "status"], name="jour_block_step_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.step_id and self.journey_id and self.step.journey_id != self.journey_id:
            raise ValidationError({"step": "Le blocker et la Step doivent appartenir à la même Journey."})
        if self.status in {JourneyBlockerStatus.RESOLVED, JourneyBlockerStatus.WAIVED} and not self.resolved_at:
            raise ValidationError({"resolved_at": "Un blocker fermé doit conserver sa date de résolution."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = JourneyBlocker.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service de résolution des blockers."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def delete(self, *args, **kwargs):
        raise ValidationError("Un blocker Journey est un historique métier et ne peut pas être supprimé.")


class JourneyAssignmentResponsibility(models.TextChoices):
    LEAD = "lead", "Responsable principal"
    FACILITATOR = "facilitator", "Facilitateur"
    REVIEWER = "reviewer", "Reviewer"
    SUPPORT = "support", "Support"


class JourneyAssignmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ENDED = "ended", "Terminée"
    CANCELLED = "cancelled", "Annulée"


class JourneyAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey("journeys.Journey", on_delete=models.CASCADE, related_name="assignments")
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="journey_assignments")
    responsibility = models.CharField(max_length=20, choices=JourneyAssignmentResponsibility.choices)
    status = models.CharField(max_length=16, choices=JourneyAssignmentStatus.choices, default=JourneyAssignmentStatus.ACTIVE)
    is_primary = models.BooleanField(default=False)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="journey_assignments_created",
        null=True,
        blank=True,
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["journey", "responsibility", "assigned_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["journey"],
                condition=Q(
                    responsibility=JourneyAssignmentResponsibility.LEAD,
                    is_primary=True,
                    status=JourneyAssignmentStatus.ACTIVE,
                ),
                name="jour_assignment_one_primary_lead",
            ),
            models.UniqueConstraint(
                fields=["journey", "profile", "responsibility"],
                condition=Q(status=JourneyAssignmentStatus.ACTIVE),
                name="jour_assignment_active_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["journey", "status"], name="jour_assign_journey_status_idx"),
            models.Index(fields=["profile", "status"], name="jour_assign_profile_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.is_primary and self.responsibility != JourneyAssignmentResponsibility.LEAD:
            raise ValidationError({"is_primary": "Seul un lead peut être l’affectation primaire."})
        if self.status != JourneyAssignmentStatus.ACTIVE and not self.ended_at:
            raise ValidationError({"ended_at": "Une affectation fermée doit conserver sa date de fin."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = JourneyAssignment.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service d’affectation Journey."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result


class JourneyStepAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step = models.ForeignKey(JourneyStep, on_delete=models.CASCADE, related_name="assignments")
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="journey_step_assignments")
    responsibility = models.CharField(max_length=20, choices=JourneyAssignmentResponsibility.choices)
    status = models.CharField(max_length=16, choices=JourneyAssignmentStatus.choices, default=JourneyAssignmentStatus.ACTIVE)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="journey_step_assignments_created",
        null=True,
        blank=True,
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["step", "profile", "responsibility"],
                condition=Q(status=JourneyAssignmentStatus.ACTIVE),
                name="jour_step_assignment_active_unique",
            )
        ]
        indexes = [models.Index(fields=["step", "status"], name="jour_step_assign_status_idx")]

    def clean(self):
        super().clean()
        if self.status != JourneyAssignmentStatus.ACTIVE and not self.ended_at:
            raise ValidationError({"ended_at": "Une affectation fermée doit conserver sa date de fin."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = JourneyStepAssignment.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service d’affectation JourneyStep."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result


def journey_artifact_upload_to(instance, filename):
    return f"journeys/{instance.journey_id}/{instance.id}.bin"


class JourneyArtifactKind(models.TextChoices):
    CV = "cv", "CV"
    COVER_LETTER = "cover_letter", "Lettre de motivation"
    CERTIFICATE = "certificate", "Certificat"
    TRANSCRIPT = "transcript", "Relevé"
    RECOMMENDATION = "recommendation", "Recommandation"
    IDENTITY_DOCUMENT = "identity_document", "Document d’identité"
    FORM = "form", "Formulaire"
    PAYMENT_RECEIPT = "payment_receipt", "Reçu de paiement"
    OTHER = "other", "Autre"


class JourneyArtifactStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    SUBMITTED = "submitted", "Soumis"
    IN_REVIEW = "in_review", "En revue"
    ACCEPTED = "accepted", "Accepté"
    REJECTED = "rejected", "À corriger"
    SUPERSEDED = "superseded", "Remplacé"


class JourneyArtifactSensitivity(models.TextChoices):
    NORMAL = "normal", "Normale"
    SENSITIVE = "sensitive", "Sensible"
    RESTRICTED = "restricted", "Restreinte"


class JourneyArtifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey("journeys.Journey", on_delete=models.CASCADE, related_name="artifacts")
    step = models.ForeignKey(JourneyStep, on_delete=models.PROTECT, related_name="artifacts", null=True, blank=True)
    kind = models.CharField(max_length=32, choices=JourneyArtifactKind.choices, default=JourneyArtifactKind.OTHER)
    title = models.CharField(max_length=220)
    file = models.FileField(storage=private_artifact_storage, upload_to=journey_artifact_upload_to, max_length=500)
    status = models.CharField(max_length=16, choices=JourneyArtifactStatus.choices, default=JourneyArtifactStatus.DRAFT)
    sensitivity = models.CharField(max_length=16, choices=JourneyArtifactSensitivity.choices, default=JourneyArtifactSensitivity.NORMAL)
    supersedes = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        related_name="superseded_by",
        null=True,
        blank=True,
    )
    version = models.PositiveIntegerField(default=1)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_journey_artifacts",
    )
    uploaded_at = models.DateTimeField(default=timezone.now)
    size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=180)
    content_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["journey", "kind", "title", "version", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["journey", "kind", "title", "version"], name="jour_artifact_version_unique"),
            models.CheckConstraint(condition=Q(version__gte=1), name="jour_artifact_version_positive"),
        ]
        indexes = [
            models.Index(fields=["journey", "status"], name="jour_art_journey_status_idx"),
            models.Index(fields=["journey", "sensitivity"], name="jour_art_journey_sens_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.step_id and self.journey_id and self.step.journey_id != self.journey_id:
            errors["step"] = "L’Artifact et la Step doivent appartenir à la même Journey."
        if self.supersedes_id:
            previous = self.supersedes
            if previous.journey_id != self.journey_id or previous.kind != self.kind or previous.title != self.title:
                errors["supersedes"] = "Une version ne peut remplacer qu’un Artifact de la même série."
            elif self.version != previous.version + 1:
                errors["version"] = "La version doit suivre exactement la version remplacée."
        elif self.version != 1:
            errors["version"] = "La première version d’une série doit être la version 1."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = JourneyArtifact.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez les services JourneyArtifact pour changer le statut."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def delete(self, *args, **kwargs):
        raise ValidationError("Un Artifact Journey versionné ne peut pas être supprimé silencieusement.")


class JourneyArtifactReviewStatus(models.TextChoices):
    REQUESTED = "requested", "Demandée"
    IN_PROGRESS = "in_progress", "En cours"
    APPROVED = "approved", "Approuvée"
    CHANGES_REQUESTED = "changes_requested", "Modifications demandées"
    CANCELLED = "cancelled", "Annulée"


class JourneyArtifactReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artifact = models.ForeignKey(JourneyArtifact, on_delete=models.PROTECT, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="journey_artifact_reviews")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="requested_journey_artifact_reviews",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=24, choices=JourneyArtifactReviewStatus.choices, default=JourneyArtifactReviewStatus.REQUESTED)
    comment = models.TextField(blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at", "id"]
        indexes = [models.Index(fields=["artifact", "status"], name="jour_art_review_status_idx")]

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = JourneyArtifactReview.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service de transition JourneyArtifactReview."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result


class JourneyNoteVisibility(models.TextChoices):
    BENEFICIARY_VISIBLE = "beneficiary_visible", "Visible au bénéficiaire"
    INTERNAL = "internal", "Interne"


class JourneyNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey("journeys.Journey", on_delete=models.CASCADE, related_name="notes")
    step = models.ForeignKey(JourneyStep, on_delete=models.PROTECT, related_name="notes", null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="journey_notes")
    visibility = models.CharField(max_length=24, choices=JourneyNoteVisibility.choices)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["journey", "visibility"], name="jour_note_visibility_idx")]

    def clean(self):
        super().clean()
        if self.step_id and self.journey_id and self.step.journey_id != self.journey_id:
            raise ValidationError({"step": "La note et la Step doivent appartenir à la même Journey."})
        if not (self.body or "").strip():
            raise ValidationError({"body": "Une note ne peut pas être vide."})

    def save(self, *args, **kwargs):
        self.body = (self.body or "").strip()
        self.full_clean()
        if self.pk and not self._state.adding:
            previous = JourneyNote.objects.filter(pk=self.pk).values(
                "journey_id", "step_id", "author_id", "visibility", "body"
            ).first()
            current = {
                "journey_id": self.journey_id,
                "step_id": self.step_id,
                "author_id": self.author_id,
                "visibility": self.visibility,
                "body": self.body,
            }
            if previous is not None and previous != current:
                raise ValidationError("Les JourneyNotes T31 sont append-only pour préserver l’audit.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Les JourneyNotes sont append-only dans T31.")


class JourneyPlanTemplateStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publié"
    RETIRED = "retired", "Retiré"


class JourneyPlanStepActor(models.TextChoices):
    BENEFICIARY = "beneficiary", "Bénéficiaire"
    OPERATOR = "operator", "Porteur / opérateur"


class JourneyPlanTemplate(models.Model):
    """Versioned, Activity-owned reusable Journey plan.

    This is the generic owner for new reusable Journey step plans. Vertical
    domains may reference a published version but do not copy its steps.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="journey_plan_templates",
    )
    key = models.SlugField(max_length=120)
    version = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=220)
    status = models.CharField(
        max_length=16,
        choices=JourneyPlanTemplateStatus.choices,
        default=JourneyPlanTemplateStatus.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_journey_plan_templates",
        null=True,
        blank=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["activity", "key", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "key", "version"],
                name="jour_plan_version_unique",
            ),
            models.CheckConstraint(
                condition=Q(version__gt=0),
                name="jour_plan_version_positive",
            ),
            models.UniqueConstraint(
                fields=["activity", "key"],
                condition=Q(status=JourneyPlanTemplateStatus.PUBLISHED),
                name="jour_plan_one_published",
            ),
        ]

    def save(self, *args, **kwargs):
        self.key = (self.key or "").strip()
        self.name = (self.name or "").strip()
        if self.pk and not self._state.adding:
            previous = JourneyPlanTemplate.objects.filter(pk=self.pk).values(
                "activity_id", "key", "version", "name", "status"
            ).first()
            if previous and previous["status"] in {
                JourneyPlanTemplateStatus.PUBLISHED,
                JourneyPlanTemplateStatus.RETIRED,
            }:
                structural = {
                    "activity_id": self.activity_id,
                    "key": self.key,
                    "version": self.version,
                    "name": self.name,
                }
                if any(previous[name] != value for name, value in structural.items()):
                    raise ValidationError("Un JourneyPlanTemplate publié est structurellement immuable.")
                if self.status not in {
                    JourneyPlanTemplateStatus.PUBLISHED,
                    JourneyPlanTemplateStatus.RETIRED,
                }:
                    raise ValidationError("Un plan publié peut seulement rester publié ou être retiré.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != JourneyPlanTemplateStatus.DRAFT:
            raise ValidationError("Un plan Journey publié ou retiré ne peut pas être supprimé.")
        return super().delete(*args, **kwargs)


def _journey_plan_is_editable(template_id):
    if not template_id:
        return True
    status = JourneyPlanTemplate.objects.filter(pk=template_id).values_list(
        "status", flat=True
    ).first()
    return status in {None, JourneyPlanTemplateStatus.DRAFT}


class JourneyPlanTemplateStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        JourneyPlanTemplate,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    key = models.SlugField(max_length=120)
    kind = models.CharField(
        max_length=24,
        choices=JourneyStepKind.choices,
        default=JourneyStepKind.ACTION,
    )
    actor_kind = models.CharField(
        max_length=16,
        choices=JourneyPlanStepActor.choices,
        default=JourneyPlanStepActor.BENEFICIARY,
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    relative_due_days = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["template", "position", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "key"],
                name="jour_plan_step_key_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["template", "position"],
                name="jour_plan_step_pos_idx",
            ),
        ]

    def clean(self):
        super().clean()
        self.key = (self.key or "").strip()
        self.title = (self.title or "").strip()
        errors = {}
        if not self.key:
            errors["key"] = "La clé de l'étape est obligatoire."
        if not self.title:
            errors["title"] = "Le titre de l'étape est obligatoire."
        if self.template_id and not _journey_plan_is_editable(self.template_id):
            errors["template"] = "Les étapes d'un plan publié ou retiré sont immuables."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not _journey_plan_is_editable(self.template_id):
            raise ValidationError("Les étapes d'un plan publié ou retiré sont immuables.")
        return super().delete(*args, **kwargs)


class JourneyPlanTemplateStepDependency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step = models.ForeignKey(
        JourneyPlanTemplateStep,
        on_delete=models.CASCADE,
        related_name="dependencies",
    )
    depends_on = models.ForeignKey(
        JourneyPlanTemplateStep,
        on_delete=models.CASCADE,
        related_name="dependants",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["step", "depends_on"],
                name="jour_plan_dependency_unique",
            ),
            models.CheckConstraint(
                condition=~Q(step=models.F("depends_on")),
                name="jour_plan_dependency_not_self",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.step_id and self.depends_on_id:
            if self.step_id == self.depends_on_id:
                errors["depends_on"] = "Une étape ne peut pas dépendre d'elle-même."
            elif self.step.template_id != self.depends_on.template_id:
                errors["depends_on"] = "Les dépendances doivent rester dans le même plan."
            if not _journey_plan_is_editable(self.step.template_id):
                errors["step"] = "Les dépendances d'un plan publié ou retiré sont immuables."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class JourneyPlanMaterialization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.CASCADE,
        related_name="plan_materializations",
    )
    template_step = models.ForeignKey(
        JourneyPlanTemplateStep,
        on_delete=models.PROTECT,
        related_name="materializations",
    )
    journey_step = models.OneToOneField(
        JourneyStep,
        on_delete=models.CASCADE,
        related_name="plan_materialization",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["journey", "template_step"],
                name="jour_plan_materialization_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["journey", "created_at"],
                name="jour_plan_mat_journey_idx",
            ),
        ]
