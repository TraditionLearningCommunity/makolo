"""Private media owned by a canonical Questionnaire FormVersion."""
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from journeys.storage import private_artifact_storage
from .models import FormVersion, FormQuestion, FormVersionStatus, QuestionType


def questionnaire_media_path(instance, filename):
    return f"questionnaires/{instance.form_version_id}/{instance.pk}.bin"


class QuestionnaireMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form_version = models.ForeignKey(FormVersion, related_name="media", on_delete=models.PROTECT)
    question = models.ForeignKey(FormQuestion, null=True, blank=True, related_name="media", on_delete=models.PROTECT)
    # A choice is a stable index in a particular immutable version of the JSON choices.
    choice_index = models.PositiveIntegerField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    caption = models.CharField(max_length=5000, blank=True)
    kind = models.CharField(max_length=16, choices=[
        ("image", "Image"), ("video", "Vidéo"), ("audio", "Audio"),
        ("voice", "Note vocale"), ("file", "Document"),
    ])
    file = models.FileField(storage=private_artifact_storage, upload_to=questionnaire_media_path, max_length=500)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=180)
    size = models.PositiveBigIntegerField()
    content_hash = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="questionnaire_media")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(choice_index__isnull=True) | Q(question__isnull=False),
                name="qnr_media_choice_requires_question",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.original_name = Path(self.original_name or "fichier").name[:255]
        self.caption = (self.caption or "").strip()
        self.mime_type = (self.mime_type or "").strip().lower()[:180]
        if len(self.caption) > 5000:
            errors["caption"] = "Légende trop longue."
        if self.form_version_id and self.form_version.status != FormVersionStatus.DRAFT:
            errors["form_version"] = "Les médias d'une version publiée ne peuvent pas être modifiés."
        if self.question_id:
            if self.question.form_version_id != self.form_version_id:
                errors["question"] = "Question étrangère à cette version."
        if self.choice_index is not None:
            if not self.question_id or self.question.question_type not in {
                QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE,
            } or self.choice_index >= len(self.question.choices):
                errors["choice_index"] = "Choix inexistant dans cette question."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and QuestionnaireMedia.objects.filter(pk=self.pk).exists():
            raise ValidationError("Un média publié ou ajouté est immuable ; remplacez la version.")
        self.full_clean()
        return super().save(*args, **kwargs)
