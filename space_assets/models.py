"""Durable, explicitly Space-owned documents. Not Journey or Profile assets."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from journeys.collaboration_models import JourneyArtifactKind
from journeys.storage import private_artifact_storage


class SpaceDocumentVisibility(models.TextChoices):
    INTERNAL = "internal", "Équipe autorisée"
    RESTRICTED = "restricted", "Confidentiel"


def space_document_file_path(instance, filename):
    return (
        f"space_documents/{instance.document.space_id}/"
        f"{instance.document_id}/{instance.id}.bin"
    )


class SpaceDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT,
        related_name="institutional_documents",
    )
    title = models.CharField(max_length=220)
    kind = models.CharField(
        max_length=32, choices=JourneyArtifactKind.choices,
        default=JourneyArtifactKind.OTHER,
    )
    visibility = models.CharField(
        max_length=16, choices=SpaceDocumentVisibility.choices,
        default=SpaceDocumentVisibility.RESTRICTED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="institutional_documents_created",
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="institutional_documents_archived", null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "id")
        indexes = [
            models.Index(fields=("space", "archived_at"), name="sp_doc_space_arch_idx"),
        ]

    def clean(self):
        self.title = (self.title or "").strip()
        if not self.title:
            raise ValidationError({"title": "Un titre est obligatoire."})
        if self.archived_at is None and self.archived_by_id is not None:
            raise ValidationError({"archived_by": "Archivage incohérent."})
        if self.archived_at is not None and self.archived_by_id is None:
            raise ValidationError({"archived_by": "L'auteur de l'archivage est requis."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Archivez ce document au lieu de le supprimer.")


class SpaceDocumentVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        SpaceDocument, on_delete=models.PROTECT, related_name="versions",
    )
    version = models.PositiveIntegerField()
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="superseded_by",
    )
    file = models.FileField(
        storage=private_artifact_storage,
        upload_to=space_document_file_path, max_length=500,
    )
    mime_type = models.CharField(max_length=180)
    size = models.PositiveBigIntegerField()
    content_hash = models.CharField(max_length=64)
    issued_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="institutional_document_versions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-version", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("document", "version"), name="sp_doc_version_unique",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1), name="sp_doc_version_positive",
            ),
        ]

    def clean(self):
        if self.expires_at and self.issued_at and self.expires_at < self.issued_at:
            raise ValidationError({"expires_at": "Expiration antérieure à l'émission."})
        if self.supersedes_id:
            previous = self.supersedes
            if previous.document_id != self.document_id or self.version != previous.version + 1:
                raise ValidationError("La version remplacée est incohérente.")
        elif self.version != 1:
            raise ValidationError("La première version doit être 1.")

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Une version émise est immuable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("L'historique des versions est conservé.")


class SpaceDocumentUse(models.Model):
    """Observed snapshot reuse; Requirements retains acceptance authority."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_version = models.ForeignKey(
        SpaceDocumentVersion, on_delete=models.PROTECT, related_name="uses",
    )
    journey_artifact = models.OneToOneField(
        "journeys.JourneyArtifact", on_delete=models.PROTECT,
        related_name="institutional_document_use",
    )
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="institutional_document_uses",
    )
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-used_at", "id")
