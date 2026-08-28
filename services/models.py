import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from journeys.models import JourneyStepKind, WorkflowKind


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


class ServiceJourneyContext(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.OneToOneField("journeys.Journey", on_delete=models.CASCADE, related_name="service_context")
    service_plan_template = models.ForeignKey(ServicePlanTemplate, on_delete=models.PROTECT, related_name="journey_contexts", null=True, blank=True)
    objective = models.TextField(blank=True)
    plan_materialized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]

    def clean(self):
        super().clean()
        errors = {}
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
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


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