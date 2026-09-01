import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .storage import private_resource_storage


class ResourceKind(models.TextChoices):
    TEXT = "text", "Texte / instructions"
    URL = "url", "Lien externe"
    FILE = "file", "Fichier"


class ResourceVisibility(models.TextChoices):
    PUBLIC = "public", "Public"
    PARTICIPANT = "participant", "Participant"
    RESTRICTED = "restricted", "Restreint"


class ResourceStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publiée"
    SUPERSEDED = "superseded", "Remplacée"
    RETIRED = "retired", "Retirée"


def resource_upload_to(instance, filename):
    return f"activities/{instance.activity_id}/resources/{instance.id}.bin"


class ActivityResource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey("activities.Activity", on_delete=models.CASCADE, related_name="preparation_resources")
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.CASCADE,
        related_name="preparation_resources",
        null=True,
        blank=True,
    )
    key = models.SlugField(max_length=120)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=16, choices=ResourceKind.choices)
    text_content = models.TextField(blank=True)
    external_url = models.URLField(max_length=1000, blank=True)
    file = models.FileField(storage=private_resource_storage, upload_to=resource_upload_to, max_length=500, null=True, blank=True)
    mime_type = models.CharField(max_length=180, blank=True)
    size = models.PositiveBigIntegerField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    visibility = models.CharField(max_length=16, choices=ResourceVisibility.choices, default=ResourceVisibility.PARTICIPANT)
    status = models.CharField(max_length=16, choices=ResourceStatus.choices, default=ResourceStatus.DRAFT)
    version = models.PositiveIntegerField(default=1)
    supersedes = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        related_name="superseded_by",
        null=True,
        blank=True,
    )
    significant_update = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_activity_resources")
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["activity", "occurrence", "key", "version", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "key", "version"],
                condition=Q(occurrence__isnull=True),
                name="prep_resource_activity_key_ver_unique",
            ),
            models.UniqueConstraint(
                fields=["occurrence", "key", "version"],
                condition=Q(occurrence__isnull=False),
                name="prep_resource_occ_key_ver_unique",
            ),
            models.CheckConstraint(condition=Q(version__gte=1), name="prep_resource_version_positive"),
        ]
        indexes = [
            models.Index(fields=["activity", "status", "visibility"], name="prep_resource_activity_vis_idx"),
            models.Index(fields=["occurrence", "status"], name="prep_resource_occ_status_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.occurrence_id and self.activity_id and self.occurrence.activity_id != self.activity_id:
            errors["occurrence"] = "L’Occurrence doit appartenir à l’Activity de la Resource."
        if self.kind == ResourceKind.TEXT:
            if not (self.text_content or "").strip():
                errors["text_content"] = "Une Resource texte exige des instructions."
            if self.external_url or self.file:
                errors["kind"] = "Une Resource texte ne peut pas porter simultanément URL ou fichier."
        elif self.kind == ResourceKind.URL:
            if not (self.external_url or "").strip():
                errors["external_url"] = "Une Resource URL exige un lien."
            if self.text_content or self.file:
                errors["kind"] = "Une Resource URL ne peut pas porter simultanément texte ou fichier."
        elif self.kind == ResourceKind.FILE:
            if not self.file:
                errors["file"] = "Une Resource fichier exige un fichier."
            if self.text_content or self.external_url:
                errors["kind"] = "Une Resource fichier ne peut pas porter simultanément texte ou URL."
        if self.supersedes_id:
            previous = self.supersedes
            if previous.activity_id != self.activity_id or previous.occurrence_id != self.occurrence_id or previous.key != self.key:
                errors["supersedes"] = "Une Resource ne peut remplacer qu’une version du même périmètre et de la même série."
            elif self.version != previous.version + 1:
                errors["version"] = "La version doit suivre exactement celle remplacée."
        elif self.version != 1:
            errors["version"] = "La première version doit être la version 1."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.key = (self.key or "").strip().lower()
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = ActivityResource.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez les services Resource pour changer le statut."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def delete(self, *args, **kwargs):
        raise ValidationError("Une Resource versionnée ne peut pas être supprimée silencieusement.")
