import uuid

from django.conf import settings
from django.db import models

from .enums import PresentationPurpose


class SpacePresentationDefault(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="presentation_defaults")
    purpose = models.CharField(max_length=24, choices=PresentationPurpose.choices)
    template_version = models.ForeignKey("presentations.PresentationTemplateVersion", on_delete=models.PROTECT, related_name="space_defaults")
    theme_version = models.ForeignKey("presentations.PresentationThemeVersion", on_delete=models.PROTECT, related_name="space_defaults")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_presentation_defaults")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["space", "purpose"], name="mps_space_purpose_default_unique")]


class PresentationTemplateModeration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.OneToOneField("presentations.PresentationTemplateVersion", on_delete=models.CASCADE, related_name="moderation")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_presentation_templates")
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviewed_presentation_templates", null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
