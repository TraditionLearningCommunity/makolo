import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from journeys.models import JourneyStepKind, WorkflowKind
from requirements.contracts import RequirementAssessmentState


class ServiceKind(models.TextChoices):
    APPLICATION_SUPPORT = "application_support", "Accompagnement de candidature"
    CAREER_SUPPORT = "career_support", "Accompagnement carrière"
    EDUCATION_GUIDANCE = "education_guidance", "Orientation éducative"
    DOCUMENT_SUPPORT = "document_support", "Accompagnement documentaire"
    ADMINISTRATIVE_SUPPORT = "administrative_support", "Accompagnement administratif"
    INTERVIEW_PREPARATION = "interview_preparation", "Préparation d’entretien"
    ORIENTATION = "orientation", "Orientation"
    OTHER = "other", "Autre"


class OpportunityPolicy(models.TextChoices):
    REQUIRED = "required", "Opportunity requise"
    OPTIONAL = "optional", "Opportunity facultative"
    NONE = "none", "Sans Opportunity"


class IntakePolicy(models.TextChoices):
    AUTO_CONFIRM = "auto_confirm", "Confirmation automatique"
    REVIEW_REQUIRED = "review_required", "Revue requise"


class CompletionPolicy(models.TextChoices):
    REQUIRED_STEPS = "required_steps", "Étapes obligatoires satisfaites"
    REQUIRED_STEPS_AND_SUBMISSION = "required_steps_and_submission", "Étapes obligatoires et soumission externe"


class ServiceDetails(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.OneToOneField("activities.Activity", on_delete=models.CASCADE, related_name="service_details")
    service_kind = models.CharField(max_length=32, choices=ServiceKind.choices)
    opportunity_policy = models.CharField(max_length=16, choices=OpportunityPolicy.choices, default=OpportunityPolicy.NONE)
    intake_policy = models.CharField(max_length=24, choices=IntakePolicy.choices, default=IntakePolicy.AUTO_CONFIRM)
    allows_external_beneficiary = models.BooleanField(default=False)
    completion_policy = models.CharField(max_length=32, choices=CompletionPolicy.choices, default=CompletionPolicy.REQUIRED_STEPS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["activity__title", "id"]

    def __str__(self):
        return f"Services — {self.activity}"


class ServicePlanTemplateStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publié"
    RETIRED = "retired", "Retiré"


class ServicePlanTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(ServiceDetails, on_delete=models.CASCADE, related_name="plan_templates")
    key = models.SlugField(max_length=120)
    version = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=220)
    status = models.CharField(max_length=16, choices=ServicePlanTemplateStatus.choices, default=ServicePlanTemplateStatus.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_service_plan_templates", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["service", "key", "version"]
        constraints = [
            models.UniqueConstraint(fields=["service", "key", "version"], name="services_plan_version_unique"),
            models.CheckConstraint(condition=Q(version__gte=1), name="services_plan_version_positive"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = ServicePlanTemplate.objects.filter(pk=self.pk).values("service_id", "key", "version", "name", "status").first()
            if previous and previous["status"] == ServicePlanTemplateStatus.PUBLISHED:
                structural = {"service_id": self.service_id, "key": self.key, "version": self.version, "name": self.name}
                if any(previous[name] != value for name, value in structural.items()):
                    raise ValidationError("Un ServicePlanTemplate publié est structurellement immuable.")
                if self.status not in {ServicePlanTemplateStatus.PUBLISHED, ServicePlanTemplateStatus.RETIRED}:
                    raise ValidationError("Un template publié peut seulement rester publié ou être retiré.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        persisted_status = _persisted_template_status(self.pk)
        if persisted_status and persisted_status != ServicePlanTemplateStatus.DRAFT:
            raise ValidationError("Un ServicePlanTemplate publié ou retiré ne peut pas être supprimé.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.service.activity} — {self.key} v{self.version}"


def _persisted_template_status(template_id):
    if not template_id:
        return None
    return ServicePlanTemplate.objects.filter(pk=template_id).values_list("status", flat=True).first()


class ServicePlanTemplateStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(ServicePlanTemplate, on_delete=models.CASCADE, related_name="steps")
    kind = models.CharField(max_length=24, choices=JourneyStepKind.choices, default=JourneyStepKind.ACTION)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    relative_due_days = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["template", "position", "created_at", "id"]
        indexes = [models.Index(fields=["template", "position"], name="services_tpl_step_pos_idx")]

    def save(self, *args, **kwargs):
        template_status = _persisted_template_status(self.template_id)
        if template_status and template_status != ServicePlanTemplateStatus.DRAFT:
            if self._state.adding:
                raise ValidationError("Les étapes d’un template publié ou retiré sont immuables.")
            previous = ServicePlanTemplateStep.objects.filter(pk=self.pk).values("template_id", "kind", "title", "description", "position", "is_required", "relative_due_days").first()
            current = {"template_id": self.template_id, "kind": self.kind, "title": self.title, "description": self.description, "position": self.position, "is_required": self.is_required, "relative_due_days": self.relative_due_days}
            if previous != current:
                raise ValidationError("Les étapes d’un template publié ou retiré sont immuables.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        template_status = _persisted_template_status(self.template_id)
        if template_status and template_status != ServicePlanTemplateStatus.DRAFT:
            raise ValidationError("Les étapes d’un template publié ou retiré sont immuables.")
        return super().delete(*args, **kwargs)


class ServicePlanTemplateStepDependency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step = models.ForeignKey(ServicePlanTemplateStep, on_delete=models.CASCADE, related_name="dependencies")
    depends_on = models.ForeignKey(ServicePlanTemplateStep, on_delete=models.CASCADE, related_name="dependants")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["step", "depends_on"], name="services_tpl_dependency_unique"),
            models.CheckConstraint(condition=~Q(step=models.F("depends_on")), name="services_tpl_dependency_not_self"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.step_id and self.depends_on_id:
            if self.step_id == self.depends_on_id:
                errors["depends_on"] = "Une étape de template ne peut pas dépendre d’elle-même."
            elif self.step.template_id != self.depends_on.template_id:
                errors["depends_on"] = "Les dépendances doivent rester dans le même template versionné."
            template_status = _persisted_template_status(self.step.template_id)
            if template_status and template_status != ServicePlanTemplateStatus.DRAFT:
                errors["step"] = "Les dépendances d’un template publié ou retiré sont immuables."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        template_status = _persisted_template_status(self.step.template_id)
        if template_status and template_status != ServicePlanTemplateStatus.DRAFT:
            raise ValidationError("Les dépendances d’un template publié ou retiré sont immuables.")
        return super().delete(*args, **kwargs)


class ServiceCurrentOutcome(models.TextChoices):
    NOT_SUBMITTED = "not_submitted", "Non soumis"
    SUBMITTED = "submitted", "Soumis"
    ACKNOWLEDGED = "acknowledged", "Réception accusée"
    UNDER_REVIEW = "under_review", "En revue"
    ACTION_REQUIRED = "action_required", "Action requise"
    INTERVIEW = "interview", "Entretien"
    SUCCESSFUL = "successful", "Succès"
    UNSUCCESSFUL = "unsuccessful", "Échec externe"
    WITHDRAWN = "withdrawn", "Retiré"
    UNKNOWN = "unknown", "Inconnu"


class ServiceJourneyContext(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.OneToOneField("journeys.Journey", on_delete=models.CASCADE, related_name="service_context")
    service_plan_template = models.ForeignKey(ServicePlanTemplate, on_delete=models.PROTECT, related_name="journey_contexts", null=True, blank=True)
    opportunity = models.ForeignKey("opportunities.Opportunity", on_delete=models.PROTECT, related_name="service_contexts", null=True, blank=True)
    opportunity_revision = models.ForeignKey("opportunities.OpportunityRevision", on_delete=models.PROTECT, related_name="service_contexts", null=True, blank=True)
    objective = models.TextField(blank=True)
    plan_materialized_at = models.DateTimeField(null=True, blank=True)
    current_outcome = models.CharField(max_length=24, choices=ServiceCurrentOutcome.choices, default=ServiceCurrentOutcome.NOT_SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(opportunity__isnull=True, opportunity_revision__isnull=True)
                    | Q(opportunity__isnull=False, opportunity_revision__isnull=False)
                ),
                name="services_context_opp_pair",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if bool(self.opportunity_id) != bool(self.opportunity_revision_id):
            errors["opportunity"] = "Opportunity et OpportunityRevision doivent être renseignées ensemble."
        if self.journey_id:
            if self.journey.workflow != WorkflowKind.SERVICE:
                errors["journey"] = "ServiceJourneyContext exige une Journey de workflow SERVICE."
            try:
                service = self.journey.activity.service_details
            except ServiceDetails.DoesNotExist:
                errors["journey"] = "L’Activity de la Journey ne possède pas de ServiceDetails."
            else:
                if self.service_plan_template_id and self.service_plan_template.service_id != service.pk:
                    errors["service_plan_template"] = "Le template doit appartenir au Service de la Journey."
                if service.opportunity_policy == OpportunityPolicy.NONE and self.opportunity_id:
                    errors["opportunity"] = "Ce Service est configuré sans Opportunity."
        if self.opportunity_revision_id:
            if self.opportunity_revision.opportunity_id != self.opportunity_id:
                errors["opportunity_revision"] = "La révision pinnée doit appartenir à l’Opportunity sélectionnée."
            if self.opportunity_revision.published_at is None:
                errors["opportunity_revision"] = "Une Journey Services doit pinner une OpportunityRevision publiée."
        if self.pk and not self._state.adding:
            previous = ServiceJourneyContext.objects.filter(pk=self.pk).values("opportunity_id", "opportunity_revision_id", "current_outcome").first()
            if previous and not getattr(self, "_allow_opportunity_change", False) and (
                previous["opportunity_id"] != self.opportunity_id
                or previous["opportunity_revision_id"] != self.opportunity_revision_id
            ):
                errors["opportunity_revision"] = "Utilisez le service d’adoption explicite pour changer la révision pinnée."
            if previous and not getattr(self, "_allow_outcome_projection", False) and previous["current_outcome"] != self.current_outcome:
                errors["current_outcome"] = "current_outcome est une projection contrôlée par les services Outcomes."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_opportunity_change = False
        self._allow_outcome_projection = False
        return result


class ServiceRequirementAssessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    context = models.ForeignKey(ServiceJourneyContext, on_delete=models.CASCADE, related_name="requirement_assessments")
    requirement = models.ForeignKey("opportunities.OpportunityRequirement", on_delete=models.PROTECT, related_name="service_assessments")
    status = models.CharField(max_length=20, choices=RequirementAssessmentState.choices, default=RequirementAssessmentState.UNASSESSED)
    note = models.TextField(blank=True)
    assessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="service_requirement_assessments", null=True, blank=True)
    assessed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["context", "requirement__position", "created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["context", "requirement"], name="services_req_assessment_unique")]
        indexes = [
            models.Index(fields=["context", "status"], name="services_req_assess_status_idx"),
            models.Index(fields=["requirement", "status"], name="services_req_status_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.context_id and self.requirement_id:
            if self.context.opportunity_revision_id is None:
                errors["context"] = "Une Assessment exige une OpportunityRevision pinnée."
            elif self.requirement.revision_id != self.context.opportunity_revision_id:
                errors["requirement"] = "Le Requirement doit appartenir à la révision actuellement pinnée."
        if self.status == RequirementAssessmentState.UNASSESSED:
            if self.assessed_at is not None:
                errors["assessed_at"] = "Une Assessment non évaluée ne porte pas de date d’évaluation."
        elif self.assessed_at is None:
            errors["assessed_at"] = "Une Assessment évaluée doit conserver sa date d’évaluation."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and not getattr(self, "_allow_assessment_transition", False):
            previous = ServiceRequirementAssessment.objects.filter(pk=self.pk).values("status", "note", "assessed_by_id", "assessed_at").first()
            current = {"status": self.status, "note": self.note, "assessed_by_id": self.assessed_by_id, "assessed_at": self.assessed_at}
            if previous and previous != current:
                raise ValidationError("Utilisez le service d’évaluation des Requirements.")
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_assessment_transition = False
        return result

    def delete(self, *args, **kwargs):
        raise ValidationError("Une Assessment Requirement fait partie de l’historique du dossier et ne peut pas être supprimée.")


class ServiceRequirementEvidenceStatus(models.TextChoices):
    SUBMITTED = "submitted", "Soumise"
    ACCEPTED = "accepted", "Acceptée"
    REJECTED = "rejected", "Rejetée"


class ServiceRequirementEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(ServiceRequirementAssessment, on_delete=models.PROTECT, related_name="evidence")
    artifact = models.ForeignKey("journeys.JourneyArtifact", on_delete=models.PROTECT, related_name="requirement_evidence")
    status = models.CharField(max_length=16, choices=ServiceRequirementEvidenceStatus.choices, default=ServiceRequirementEvidenceStatus.SUBMITTED)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="submitted_service_requirement_evidence", null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="reviewed_service_requirement_evidence", null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assessment", "artifact"], name="services_req_evidence_unique")]
        indexes = [models.Index(fields=["assessment", "status"], name="services_req_evid_status_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.assessment_id and self.artifact_id and self.assessment.context.journey_id != self.artifact.journey_id:
            errors["artifact"] = "La preuve doit être un JourneyArtifact du même dossier."
        if self.status == ServiceRequirementEvidenceStatus.SUBMITTED:
            if self.reviewed_at is not None or self.reviewed_by_id is not None:
                errors["reviewed_at"] = "Une preuve soumise n’est pas encore revue."
        elif self.reviewed_at is None:
            errors["reviewed_at"] = "Une preuve acceptée ou rejetée doit conserver sa date de revue."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and not getattr(self, "_allow_evidence_transition", False):
            previous = ServiceRequirementEvidence.objects.filter(pk=self.pk).values("status", "reviewed_by_id", "reviewed_at", "review_note").first()
            current = {"status": self.status, "reviewed_by_id": self.reviewed_by_id, "reviewed_at": self.reviewed_at, "review_note": self.review_note}
            if previous and previous != current:
                raise ValidationError("Utilisez le service de revue des preuves Requirement.")
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_evidence_transition = False
        return result

    def delete(self, *args, **kwargs):
        raise ValidationError("Une preuve Requirement auditée ne peut pas être supprimée.")


class ServiceOpportunityRevisionAdoption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    context = models.ForeignKey(ServiceJourneyContext, on_delete=models.CASCADE, related_name="opportunity_revision_adoptions")
    previous_revision = models.ForeignKey("opportunities.OpportunityRevision", on_delete=models.PROTECT, related_name="service_adoptions_from")
    revision = models.ForeignKey("opportunities.OpportunityRevision", on_delete=models.PROTECT, related_name="service_adoptions_to")
    adopted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="service_opportunity_revision_adoptions", null=True, blank=True)
    adopted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["context", "adopted_at", "id"]
        constraints = [models.UniqueConstraint(fields=["context", "revision"], name="services_opp_adoption_unique")]
        indexes = [models.Index(fields=["context", "adopted_at"], name="services_opp_adopt_ctx_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.previous_revision_id and self.revision_id:
            if self.previous_revision.opportunity_id != self.revision.opportunity_id:
                errors["revision"] = "Les révisions d’adoption doivent appartenir à la même Opportunity."
            if self.revision.version <= self.previous_revision.version:
                errors["revision"] = "L’adoption doit avancer vers une version plus récente."
        if self.context_id and self.revision_id and self.context.opportunity_id != self.revision.opportunity_id:
            errors["context"] = "L’adoption doit rester sur l’Opportunity du contexte."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Un audit d’adoption Opportunity est append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un audit d’adoption Opportunity ne peut pas être supprimé.")


class ServiceRequirementStepLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(ServiceRequirementAssessment, on_delete=models.PROTECT, related_name="step_links")
    journey_step = models.ForeignKey("journeys.JourneyStep", on_delete=models.PROTECT, related_name="requirement_links")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_service_requirement_step_links", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assessment", "journey_step"], name="services_req_step_link_unique")]
        indexes = [models.Index(fields=["assessment"], name="services_req_step_link_idx")]

    def clean(self):
        super().clean()
        if self.assessment_id and self.journey_step_id and self.journey_step.journey_id != self.assessment.context.journey_id:
            raise ValidationError({"journey_step": "La JourneyStep doit appartenir au dossier de l’Assessment."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ServiceRequirementPaymentObligation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(ServiceRequirementAssessment, on_delete=models.PROTECT, related_name="payment_obligation_links")
    obligation = models.ForeignKey("payments.PaymentObligation", on_delete=models.PROTECT, related_name="service_requirement_links")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_requirement_payment_links", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assessment", "obligation"], name="services_req_payment_obligation_unique")]
        indexes = [models.Index(fields=["assessment"], name="services_req_payobl_assess_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.assessment_id and self.obligation_id:
            if self.assessment.requirement.kind != "financial":
                errors["assessment"] = "Seul un Requirement financier peut être lié à une PaymentObligation."
            if self.assessment.context.journey_id != self.obligation.journey_id:
                errors["obligation"] = "L’obligation doit appartenir à la Journey de l’Assessment."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ServiceSubmissionMode(models.TextChoices):
    EXTERNAL_WEB = "external_web", "Portail web externe"
    EMAIL = "email", "E-mail"
    IN_PERSON = "in_person", "En personne"
    MAKOLO_INTEGRATED = "makolo_integrated", "Intégration Makolo"
    OTHER = "other", "Autre"


class ServiceSubmissionStatus(models.TextChoices):
    PREPARED = "prepared", "Préparée"
    SUBMITTED = "submitted", "Soumise"
    ACKNOWLEDGED = "acknowledged", "Réception accusée"
    FAILED = "failed", "Échouée"
    WITHDRAWN = "withdrawn", "Retirée"


class ServiceSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    context = models.ForeignKey(ServiceJourneyContext, on_delete=models.PROTECT, related_name="submissions")
    attempt = models.PositiveIntegerField()
    mode = models.CharField(max_length=24, choices=ServiceSubmissionMode.choices)
    status = models.CharField(max_length=16, choices=ServiceSubmissionStatus.choices, default=ServiceSubmissionStatus.PREPARED)
    submitted_at = models.DateTimeField(null=True, blank=True)
    external_reference = models.CharField(max_length=240, blank=True)
    receipt_artifact = models.ForeignKey("journeys.JourneyArtifact", on_delete=models.PROTECT, related_name="service_submission_receipts", null=True, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="service_submissions", null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["context", "attempt", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["context", "attempt"], name="services_submission_attempt_unique"),
            models.CheckConstraint(condition=Q(attempt__gte=1), name="services_submission_attempt_positive"),
        ]
        indexes = [
            models.Index(fields=["context", "status"], name="services_submission_status_idx"),
            models.Index(fields=["context", "attempt"], name="services_sub_attempt_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.receipt_artifact_id and self.receipt_artifact.journey_id != self.context.journey_id:
            errors["receipt_artifact"] = "Le reçu de soumission doit appartenir à la Journey du contexte."
        if self.status in {ServiceSubmissionStatus.SUBMITTED, ServiceSubmissionStatus.ACKNOWLEDGED} and self.submitted_at is None:
            errors["submitted_at"] = "Une soumission réellement envoyée doit conserver submitted_at."
        if self.status == ServiceSubmissionStatus.PREPARED and self.submitted_at is not None:
            errors["submitted_at"] = "Une tentative seulement préparée ne porte pas encore submitted_at."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = ServiceSubmission.objects.filter(pk=self.pk).values("status", "submitted_at", "failure_reason", "external_reference", "receipt_artifact_id").first()
            current = {"status": self.status, "submitted_at": self.submitted_at, "failure_reason": self.failure_reason, "external_reference": self.external_reference, "receipt_artifact_id": self.receipt_artifact_id}
            if previous and previous != current:
                raise ValidationError("Utilisez les services Services pour modifier une tentative de soumission.")
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def delete(self, *args, **kwargs):
        raise ValidationError("Une tentative de soumission auditée ne peut pas être supprimée.")


class ServiceOutcomeEventType(models.TextChoices):
    SUBMITTED = "submitted", "Soumis"
    ACKNOWLEDGED = "acknowledged", "Réception accusée"
    UNDER_REVIEW = "under_review", "En revue"
    ACTION_REQUIRED = "action_required", "Action requise"
    INTERVIEW = "interview", "Entretien"
    SUCCESSFUL = "successful", "Succès"
    UNSUCCESSFUL = "unsuccessful", "Échec externe"
    WITHDRAWN = "withdrawn", "Retiré"
    OTHER = "other", "Autre"


class ServiceOutcomeEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    context = models.ForeignKey(ServiceJourneyContext, on_delete=models.PROTECT, related_name="outcome_events")
    event_type = models.CharField(max_length=24, choices=ServiceOutcomeEventType.choices)
    occurred_at = models.DateTimeField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="recorded_service_outcomes", null=True, blank=True)
    note = models.TextField(blank=True)
    external_reference = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["context", "occurred_at", "created_at", "id"]
        indexes = [models.Index(fields=["context", "occurred_at"], name="services_outcome_time_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("ServiceOutcomeEvent est append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("ServiceOutcomeEvent est append-only.")


class ServicePlanMaterialization(models.Model):
    """Vertical-owned trace from template snapshot to generic JourneyStep."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    context = models.ForeignKey(ServiceJourneyContext, on_delete=models.CASCADE, related_name="materialized_steps")
    template_step = models.ForeignKey(ServicePlanTemplateStep, on_delete=models.PROTECT, related_name="materializations")
    journey_step = models.OneToOneField("journeys.JourneyStep", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["context", "template_step"], name="services_materialization_step_unique")]

    def clean(self):
        super().clean()
        errors = {}
        if self.context_id and self.template_step_id and self.context.service_plan_template_id != self.template_step.template_id:
            errors["template_step"] = "La TemplateStep doit appartenir au template matérialisé."
        if self.context_id and self.journey_step_id and self.context.journey_id != self.journey_step.journey_id:
            errors["journey_step"] = "La JourneyStep doit appartenir à la Journey du contexte."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ServiceIntakeQuestionType(models.TextChoices):
    SHORT_TEXT = "short_text", "Texte court"
    LONG_TEXT = "long_text", "Texte long"
    BOOLEAN = "boolean", "Oui / non"
    DATE = "date", "Date"
    SINGLE_CHOICE = "single_choice", "Choix unique"
    MULTIPLE_CHOICE = "multiple_choice", "Choix multiples"


class ServiceIntakeQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(ServiceDetails, on_delete=models.CASCADE, related_name="intake_questions", null=True, blank=True)
    template = models.ForeignKey(ServicePlanTemplate, on_delete=models.CASCADE, related_name="intake_questions", null=True, blank=True)
    key = models.SlugField(max_length=120)
    prompt = models.CharField(max_length=500)
    question_type = models.CharField(max_length=24, choices=ServiceIntakeQuestionType.choices)
    is_required = models.BooleanField(default=True)
    options = models.JSONField(default=list, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=(Q(service__isnull=False) & Q(template__isnull=True)) | (Q(service__isnull=True) & Q(template__isnull=False)), name="services_intake_question_one_target"),
            models.UniqueConstraint(fields=["service", "key"], condition=Q(service__isnull=False), name="services_intake_service_key_unique"),
            models.UniqueConstraint(fields=["template", "key"], condition=Q(template__isnull=False), name="services_intake_template_key_unique"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if bool(self.service_id) == bool(self.template_id):
            errors["service"] = "Une question Intake cible exactement un Service ou une version de template."
        if not isinstance(self.options, list) or any(not isinstance(item, str) or not item.strip() for item in self.options):
            errors["options"] = "Les options doivent être une liste de chaînes non vides."
        if len(set(self.options)) != len(self.options):
            errors["options"] = "Les options doivent être uniques."
        if self.question_type in {ServiceIntakeQuestionType.SINGLE_CHOICE, ServiceIntakeQuestionType.MULTIPLE_CHOICE}:
            if not self.options:
                errors["options"] = "Une question à choix exige au moins une option."
        elif self.options:
            errors["options"] = "Les options ne sont permises que pour les questions à choix."
        if self.template_id:
            template_status = _persisted_template_status(self.template_id)
            if template_status and template_status != ServicePlanTemplateStatus.DRAFT:
                if self._state.adding:
                    errors["template"] = "Un template publié ou retiré ne peut plus recevoir de question Intake."
                else:
                    previous = ServiceIntakeQuestion.objects.filter(pk=self.pk).values("service_id", "template_id", "key", "prompt", "question_type", "is_required", "options", "position").first()
                    current = {"service_id": self.service_id, "template_id": self.template_id, "key": self.key, "prompt": self.prompt, "question_type": self.question_type, "is_required": self.is_required, "options": self.options, "position": self.position}
                    if previous != current:
                        errors["template"] = "Les questions Intake d’un template publié ou retiré sont immuables."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.options = [item.strip() for item in (self.options or [])]
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.template_id:
            template_status = _persisted_template_status(self.template_id)
            if template_status and template_status != ServicePlanTemplateStatus.DRAFT:
                raise ValidationError("Les questions Intake d’un template publié ou retiré sont immuables.")
        return super().delete(*args, **kwargs)


class ServiceIntakeAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey("journeys.Journey", on_delete=models.CASCADE, related_name="service_intake_answers")
    question = models.ForeignKey(ServiceIntakeQuestion, on_delete=models.PROTECT, related_name="answers")
    value = models.JSONField()
    answered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="service_intake_answers", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["journey", "question"], name="services_intake_answer_unique")]
        indexes = [models.Index(fields=["journey", "created_at"], name="services_intake_answer_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.journey_id:
            if self.journey.workflow != WorkflowKind.SERVICE:
                errors["journey"] = "Une réponse Intake Services exige une Journey SERVICE."
            else:
                try:
                    service = self.journey.activity.service_details
                except ServiceDetails.DoesNotExist:
                    errors["journey"] = "L’Activity de la Journey n’est pas un Service."
                else:
                    if self.question_id:
                        if self.question.service_id and self.question.service_id != service.pk:
                            errors["question"] = "Cette question appartient à un autre Service."
                        if self.question.template_id:
                            try:
                                context = self.journey.service_context
                            except ServiceJourneyContext.DoesNotExist:
                                errors["question"] = "La Journey ne possède pas de contexte Services."
                            else:
                                if context.service_plan_template_id != self.question.template_id:
                                    errors["question"] = "Cette question appartient à une autre version de plan."
        if self.question_id:
            try:
                validate_intake_value(self.question, self.value)
            except ValidationError as exc:
                errors["value"] = exc.messages
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = ServiceIntakeAnswer.objects.select_related("journey").get(pk=self.pk)
            if previous.journey.status != "draft":
                raise ValidationError("Les réponses Intake sont figées après la soumission de la Journey.")
        self.full_clean()
        return super().save(*args, **kwargs)


def validate_intake_value(question, value):
    kind = question.question_type
    if kind in {ServiceIntakeQuestionType.SHORT_TEXT, ServiceIntakeQuestionType.LONG_TEXT}:
        if not isinstance(value, str):
            raise ValidationError("Une réponse texte doit être une chaîne.")
        if kind == ServiceIntakeQuestionType.SHORT_TEXT and len(value) > 500:
            raise ValidationError("La réponse courte dépasse 500 caractères.")
    elif kind == ServiceIntakeQuestionType.BOOLEAN:
        if type(value) is not bool:
            raise ValidationError("Une réponse booléenne doit être true ou false.")
    elif kind == ServiceIntakeQuestionType.DATE:
        if not isinstance(value, str):
            raise ValidationError("Une date Intake doit être une date ISO YYYY-MM-DD.")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValidationError("Date Intake invalide.") from exc
        if parsed.isoformat() != value:
            raise ValidationError("Une date Intake doit utiliser le format ISO YYYY-MM-DD.")
    elif kind == ServiceIntakeQuestionType.SINGLE_CHOICE:
        if not isinstance(value, str) or value not in question.options:
            raise ValidationError("Le choix sélectionné n’est pas autorisé.")
    elif kind == ServiceIntakeQuestionType.MULTIPLE_CHOICE:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValidationError("Les choix multiples doivent être une liste de chaînes.")
        if len(set(value)) != len(value) or any(item not in question.options for item in value):
            raise ValidationError("Un ou plusieurs choix ne sont pas autorisés.")
    else:
        raise ValidationError("Type de question Intake inconnu.")
