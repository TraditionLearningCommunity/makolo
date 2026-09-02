import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from journeys.storage import private_artifact_storage


class InboundCaptureSourceKind(models.TextChoices):
    URL = "url", "Lien"
    TEXT = "text", "Texte"
    FILE = "file", "Fichier"


class InboundCaptureStatus(models.TextChoices):
    PENDING = "pending", "À classer"
    ABSORBED = "absorbed", "Ajouté"
    DISCARDED = "discarded", "Ignoré"
    EXPIRED = "expired", "Expiré"


def default_capture_expiry():
    return timezone.now() + timedelta(days=7)


def inbound_capture_upload_to(instance, filename):
    return f"sharing/inbound/{instance.created_by_id}/{instance.id}.bin"


class InboundCapture(models.Model):
    """Private staging object. Canonical ownership moves to the destination domain on absorption."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbound_captures",
    )
    source_kind = models.CharField(max_length=12, choices=InboundCaptureSourceKind.choices)
    status = models.CharField(
        max_length=12,
        choices=InboundCaptureStatus.choices,
        default=InboundCaptureStatus.PENDING,
    )
    source_url = models.URLField(max_length=2048, blank=True)
    text = models.TextField(blank=True)
    file = models.FileField(
        storage=private_artifact_storage,
        upload_to=inbound_capture_upload_to,
        max_length=500,
        blank=True,
    )
    original_filename = models.CharField(max_length=180, blank=True)
    mime_type = models.CharField(max_length=180, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    expires_at = models.DateTimeField(default=default_capture_expiry)
    absorbed_artifact = models.OneToOneField(
        "journeys.JourneyArtifact",
        on_delete=models.PROTECT,
        related_name="inbound_capture_origin",
        null=True,
        blank=True,
    )
    absorbed_note = models.OneToOneField(
        "journeys.JourneyNote",
        on_delete=models.PROTECT,
        related_name="inbound_capture_origin",
        null=True,
        blank=True,
    )
    absorbed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["created_by", "status", "created_at"], name="sharing_capture_owner_idx"),
            models.Index(fields=["status", "expires_at"], name="sharing_capture_expiry_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        has_url = bool((self.source_url or "").strip())
        has_text = bool((self.text or "").strip())
        has_file = bool(self.file)
        if self.status == InboundCaptureStatus.PENDING:
            if self.source_kind == InboundCaptureSourceKind.URL and not has_url:
                errors["source_url"] = "Un lien est obligatoire."
            elif self.source_kind == InboundCaptureSourceKind.TEXT and not has_text:
                errors["text"] = "Le texte ne peut pas être vide."
            elif self.source_kind == InboundCaptureSourceKind.FILE and not has_file:
                errors["file"] = "Un fichier est obligatoire."
        if self.status == InboundCaptureStatus.ABSORBED:
            if not self.absorbed_at or bool(self.absorbed_artifact_id) == bool(self.absorbed_note_id):
                errors["status"] = "Une Capture absorbée doit pointer vers exactement un résultat canonique."
        elif self.absorbed_at or self.absorbed_artifact_id or self.absorbed_note_id:
            errors["status"] = "Seule une Capture absorbée peut conserver un résultat canonique."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.status == InboundCaptureStatus.EXPIRED or (
            self.status == InboundCaptureStatus.PENDING and self.expires_at <= timezone.now()
        )
