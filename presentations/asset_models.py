import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .enums import Provenance


class PresentationAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provenance = models.CharField(max_length=16, choices=Provenance.choices)
    owner_profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="presentation_assets", null=True, blank=True)
    owner_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="presentation_assets", null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_presentation_assets")
    file = models.FileField(upload_to="presentations/assets/%Y/%m/")
    mime_type = models.CharField(max_length=80)
    size = models.PositiveIntegerField()
    checksum = models.CharField(max_length=64)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.provenance == Provenance.USER and not self.owner_profile_id:
            raise ValidationError({"owner_profile": "Un asset utilisateur exige un Profil propriétaire."})
        if self.provenance == Provenance.SPACE and not self.owner_space_id:
            raise ValidationError({"owner_space": "Un asset Espace exige un Espace propriétaire."})
        if self.provenance == Provenance.MAKOLO and (self.owner_profile_id or self.owner_space_id):
            raise ValidationError("Un asset Makolo ne porte pas de propriétaire utilisateur ou Espace.")
        if self.owner_profile_id and self.owner_space_id:
            raise ValidationError("Un asset ne peut pas avoir deux propriétaires.")

    def save(self, *args, **kwargs):
        self.full_clean(exclude={"file"} if not self.file else None)
        return super().save(*args, **kwargs)
