import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity
from journeys.storage import private_artifact_storage


def personal_asset_version_upload_to(instance, filename):
    return f"personal_assets/{instance.asset.controller_id}/{instance.asset_id}/{instance.id}.bin"


class PersonalAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    controller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="personal_assets")
    subject_profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="personal_assets_as_subject", null=True, blank=True)
    subject_external_beneficiary = models.ForeignKey("journeys.ExternalBeneficiary", on_delete=models.PROTECT, related_name="personal_assets", null=True, blank=True)
    kind = models.CharField(max_length=32, choices=JourneyArtifactKind.choices, default=JourneyArtifactKind.OTHER)
    title = models.CharField(max_length=220)
    sensitivity = models.CharField(max_length=16, choices=JourneyArtifactSensitivity.choices, default=JourneyArtifactSensitivity.NORMAL)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(subject_profile__isnull=False, subject_external_beneficiary__isnull=True) | Q(subject_profile__isnull=True, subject_external_beneficiary__isnull=False)),
                name="personal_asset_subject_xor",
            )
        ]
        indexes = [models.Index(fields=["controller", "archived_at"], name="pers_asset_ctrl_arch_idx")]

    def clean(self):
        super().clean()
        self.title = (self.title or "").strip()
        if not self.title:
            raise ValidationError({"title": "Le titre est obligatoire."})
        if bool(self.subject_profile_id) == bool(self.subject_external_beneficiary_id):
            raise ValidationError("Un élément de Ma Bibliothèque doit avoir exactement un sujet.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Archivez l’élément au lieu de le supprimer silencieusement.")


class PersonalAssetVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(PersonalAsset, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField(default=1)
    supersedes = models.OneToOneField("self", on_delete=models.PROTECT, related_name="superseded_by", null=True, blank=True)
    file = models.FileField(storage=private_artifact_storage, upload_to=personal_asset_version_upload_to, max_length=500)
    mime_type = models.CharField(max_length=180)
    size = models.PositiveBigIntegerField()
    content_hash = models.CharField(max_length=64)
    issued_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_personal_asset_versions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["asset", "version", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["asset", "version"], name="personal_asset_version_unique"),
            models.CheckConstraint(condition=Q(version__gte=1), name="personal_asset_version_positive"),
        ]
        indexes = [
            models.Index(fields=["asset", "version"], name="pers_asset_ver_idx"),
            models.Index(fields=["content_hash"], name="pers_asset_hash_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.expires_at and self.issued_at and self.expires_at < self.issued_at:
            errors["expires_at"] = "La date d’expiration ne peut pas précéder la date d’émission."
        if self.supersedes_id:
            previous = self.supersedes
            if previous.asset_id != self.asset_id:
                errors["supersedes"] = "Une version ne peut remplacer qu’une version du même élément."
            elif self.version != previous.version + 1:
                errors["version"] = "La version doit suivre exactement la version remplacée."
        elif self.version != 1:
            errors["version"] = "La première version doit être la version 1."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Une version de Ma Bibliothèque est immuable ; créez une nouvelle version.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Une version de Ma Bibliothèque ne peut pas être supprimée silencieusement.")
