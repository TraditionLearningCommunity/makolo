import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from journeys.storage import private_artifact_storage

from .point_models import ConversationPoint, ConversationPointOption, ConversationPointResponse, PointExchangeEntry


class ConversationAttachmentKind(models.TextChoices):
    FILE = "file", "Fichier"
    IMAGE = "image", "Image"
    AUDIO = "audio", "Audio"
    VOICE = "voice", "Vocal"
    VIDEO = "video", "Vidéo"


def conversation_attachment_upload_to(instance, filename):
    return f"conversations/{instance.point.conversation_id}/{instance.id}.bin"


class ConversationPointAttachment(models.Model):
    """Private media serving a Point; never a Resource, Proof or JourneyArtifact."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    point = models.ForeignKey(ConversationPoint, on_delete=models.PROTECT, related_name="attachments")
    response = models.ForeignKey(
        ConversationPointResponse,
        on_delete=models.PROTECT,
        related_name="attachments",
        null=True,
        blank=True,
    )
    exchange_entry = models.ForeignKey(
        PointExchangeEntry,
        on_delete=models.PROTECT,
        related_name="attachments",
        null=True,
        blank=True,
    )
    option = models.ForeignKey(
        ConversationPointOption, on_delete=models.PROTECT,
        related_name="attachments", null=True, blank=True,
    )
    caption = models.CharField(max_length=5000, blank=True)
    kind = models.CharField(max_length=16, choices=ConversationAttachmentKind.choices, default=ConversationAttachmentKind.FILE)
    file = models.FileField(storage=private_artifact_storage, upload_to=conversation_attachment_upload_to, max_length=500)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=180)
    size = models.PositiveBigIntegerField()
    content_hash = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conversation_attachments")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(response__isnull=True) | Q(exchange_entry__isnull=True)
                ) & (
                    Q(option__isnull=True) | (
                        Q(response__isnull=True) & Q(exchange_entry__isnull=True)
                    )
                ),
                name="conv_attachment_single_context",
            ),
        ]
        indexes = [
            models.Index(fields=["point", "created_at"], name="conv_attachment_point_idx"),
            models.Index(fields=["uploaded_by", "created_at"], name="conv_attachment_uploader_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.original_name = Path(self.original_name or "fichier").name[:255]
        self.mime_type = (self.mime_type or "application/octet-stream").strip().lower()[:180]
        self.caption = (self.caption or "").strip()
        if self.response_id and self.response.point_id != self.point_id:
            errors["response"] = "La réponse et la pièce jointe doivent appartenir au même Point."
        if self.exchange_entry_id and self.exchange_entry.point_id != self.point_id:
            errors["exchange_entry"] = "L’échange et la pièce jointe doivent appartenir au même Point."
        if self.option_id:
            if self.option.point_id != self.point_id:
                errors["option"] = "Le choix doit appartenir au même Point."
            if self.point.kind != "poll":
                errors["option"] = "Seul un Sondage possède des médias de choix."
        if sum(bool(value) for value in (self.response_id, self.exchange_entry_id, self.option_id)) > 1:
            errors["option"] = "La pièce jointe appartient à un seul contexte : Point, choix, réponse ou échange."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
