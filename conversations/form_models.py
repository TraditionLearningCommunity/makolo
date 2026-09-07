import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from questionnaires.models import FormRequest

from .point_models import ConversationPoint, ConversationPointKind


class ConversationPointFormRequest(models.Model):
    """Bridge from a Conversation Point to the canonical questionnaire request.

    Conversation owns coordination only. Questionnaire owns form structure,
    answers and submission state.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    point = models.ForeignKey(ConversationPoint, on_delete=models.CASCADE, related_name="form_request_links")
    target_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_form_request_links",
    )
    form_request = models.OneToOneField(
        FormRequest,
        on_delete=models.PROTECT,
        related_name="conversation_point_link",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["point", "target_profile"], name="conv_point_form_profile_unique"),
        ]
        indexes = [
            models.Index(fields=["target_profile", "point"], name="conv_form_profile_point_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.point_id and self.point.kind != ConversationPointKind.FORM_REQUEST:
            errors["point"] = "Le bridge FormRequest exige un Point de type Formulaire."
        if self.form_request_id:
            if self.form_request.journey_id:
                errors["form_request"] = "Un FormRequest de Conversation cible directement un Profile, pas une Journey."
            if self.target_profile_id and self.form_request.target_profile_id != self.target_profile_id:
                errors["target_profile"] = "Le Profile doit être la cible canonique du FormRequest."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
