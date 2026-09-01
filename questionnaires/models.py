import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class FormStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    ARCHIVED = "archived", "Archivé"


class FormVersionStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publiée"
    RETIRED = "retired", "Retirée"


class QuestionType(models.TextChoices):
    SHORT_TEXT = "short_text", "Texte court"
    LONG_TEXT = "long_text", "Texte long"
    BOOLEAN = "boolean", "Oui/non"
    SINGLE_CHOICE = "single_choice", "Choix unique"
    MULTIPLE_CHOICE = "multiple_choice", "Choix multiples"
    NUMBER = "number", "Nombre"
    DATE = "date", "Date"


class FormRequestStatus(models.TextChoices):
    REQUESTED = "requested", "Demandé"
    COMPLETED = "completed", "Terminé"
    CANCELLED = "cancelled", "Annulé"


class FormResponseStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    SUBMITTED = "submitted", "Soumis"
    REOPENED = "reopened", "Réouvert"


class Form(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey("activities.Activity", on_delete=models.PROTECT, related_name="forms")
    key = models.SlugField(max_length=120)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=FormStatus.choices, default=FormStatus.ACTIVE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_questionnaire_forms")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["activity", "key", "created_at"]
        constraints = [models.UniqueConstraint(fields=["activity", "key"], name="questionnaire_form_activity_key_unique")]

    def save(self, *args, **kwargs):
        self.key = (self.key or "").strip().lower()
        self.full_clean()
        return super().save(*args, **kwargs)


class FormVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(Form, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=FormVersionStatus.choices, default=FormVersionStatus.DRAFT)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_form_versions")
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["form", "version"]
        constraints = [
            models.UniqueConstraint(fields=["form", "version"], name="questionnaire_form_version_unique"),
            models.CheckConstraint(condition=Q(version__gte=1), name="questionnaire_form_version_positive"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = FormVersion.objects.filter(pk=self.pk).values("status", "title", "description").first()
            if previous and previous["status"] in {FormVersionStatus.PUBLISHED, FormVersionStatus.RETIRED}:
                if previous["title"] != self.title or previous["description"] != self.description:
                    raise ValidationError("Une version publiée est structurellement immuable.")
        self.full_clean()
        return super().save(*args, **kwargs)


class FormQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form_version = models.ForeignKey(FormVersion, on_delete=models.CASCADE, related_name="questions")
    key = models.SlugField(max_length=120)
    label = models.CharField(max_length=240)
    help_text = models.TextField(blank=True)
    question_type = models.CharField(max_length=24, choices=QuestionType.choices)
    position = models.PositiveIntegerField(default=0)
    required = models.BooleanField(default=False)
    min_length = models.PositiveIntegerField(null=True, blank=True)
    max_length = models.PositiveIntegerField(null=True, blank=True)
    min_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    max_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    choices = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["form_version", "position", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["form_version", "key"], name="questionnaire_question_version_key_unique"),
            models.UniqueConstraint(fields=["form_version", "position"], name="questionnaire_question_version_position_unique"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.form_version_id and self.form_version.status != FormVersionStatus.DRAFT:
            errors["form_version"] = "Les questions d’une version publiée ne peuvent plus être modifiées."
        if self.min_length is not None and self.max_length is not None and self.min_length > self.max_length:
            errors["max_length"] = "max_length doit être supérieur ou égal à min_length."
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            errors["max_value"] = "max_value doit être supérieur ou égal à min_value."
        if self.question_type in {QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE}:
            if not isinstance(self.choices, list) or not self.choices or any(not isinstance(v, str) or not v.strip() for v in self.choices):
                errors["choices"] = "Les questions à choix exigent une liste non vide de chaînes."
            elif len(set(self.choices)) != len(self.choices):
                errors["choices"] = "Les choix doivent être uniques."
        elif self.choices:
            errors["choices"] = "Seules les questions à choix acceptent des options."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.key = (self.key or "").strip().lower()
        self.full_clean()
        return super().save(*args, **kwargs)


class FormRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form_version = models.ForeignKey(FormVersion, on_delete=models.PROTECT, related_name="requests")
    journey = models.ForeignKey("journeys.Journey", on_delete=models.CASCADE, related_name="form_requests")
    status = models.CharField(max_length=16, choices=FormRequestStatus.choices, default=FormRequestStatus.REQUESTED)
    required = models.BooleanField(default=True)
    opens_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_form_requests")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["journey", "created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["journey", "form_version"], name="questionnaire_request_journey_version_unique")]
        indexes = [models.Index(fields=["journey", "status"], name="questionnaire_req_journey_status_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.form_version_id and self.form_version.status != FormVersionStatus.PUBLISHED:
            errors["form_version"] = "Seule une version publiée peut être demandée."
        if self.journey_id and self.form_version_id and self.journey.activity_id != self.form_version.form.activity_id:
            errors["journey"] = "La Journey et le Form doivent concerner la même Activity."
        if self.opens_at and self.due_at and self.due_at <= self.opens_at:
            errors["due_at"] = "La deadline doit être postérieure à l’ouverture."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class FormResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField(FormRequest, on_delete=models.PROTECT, related_name="response")
    form_version = models.ForeignKey(FormVersion, on_delete=models.PROTECT, related_name="responses")
    respondent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="form_responses")
    status = models.CharField(max_length=16, choices=FormResponseStatus.choices, default=FormResponseStatus.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reopened_form_responses")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["respondent", "status"], name="questionnaire_resp_user_status_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.request_id and self.form_version_id and self.request.form_version_id != self.form_version_id:
            errors["form_version"] = "La réponse doit rester liée à la version demandée."
        if self.request_id and self.respondent_id and self.request.journey.beneficiary_id != self.respondent_id:
            errors["respondent"] = "Le répondant doit être le bénéficiaire de la Journey."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class FormAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response = models.ForeignKey(FormResponse, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(FormQuestion, on_delete=models.PROTECT, related_name="answers")
    value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["response", "question"], name="questionnaire_answer_response_question_unique")]

    def clean(self):
        super().clean()
        if self.response_id and self.question_id and self.response.form_version_id != self.question.form_version_id:
            raise ValidationError({"question": "La question doit appartenir à la version de la réponse."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
