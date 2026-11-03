"""Explicit, independently publishable use of a PresentationAsset for an Activity."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class PresentationMediaPurpose(models.TextChoices):
    RECOGNIZE = "recognize", "Reconnaître"
    UNDERSTAND = "understand", "Comprendre"
    ESTABLISH = "establish", "Établir"
    PREPARE = "prepare", "Préparer"
    ACT = "act", "Agir"


class PresentationMediaState(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publié"
    RETIRED = "retired", "Retiré"


class PresentationMediaUse(models.Model):
    """One authorized use; neither owning an asset nor an Activity publishes it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey("activities.Activity", on_delete=models.CASCADE, related_name="presentation_media_uses")
    occurrence = models.ForeignKey(
        "activities.Occurrence", on_delete=models.CASCADE,
        null=True, blank=True, related_name="presentation_media_uses",
    )
    asset = models.ForeignKey("presentations.PresentationAsset", on_delete=models.PROTECT, related_name="uses")
    purpose = models.CharField(max_length=16, choices=PresentationMediaPurpose.choices)
    position = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=16, choices=PresentationMediaState.choices, default=PresentationMediaState.DRAFT)
    alt_text = models.CharField(max_length=280)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_presentation_media_uses")
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "asset", "purpose"],
                condition=Q(occurrence__isnull=True) & ~Q(state="retired"),
                name="mps_media_activity_asset_purpose_unique",
            ),
            models.UniqueConstraint(
                fields=["occurrence", "asset", "purpose"],
                condition=Q(occurrence__isnull=False) & ~Q(state="retired"),
                name="mps_media_occ_asset_purpose_unique",
            ),
            models.CheckConstraint(
                condition=Q(state="published", published_at__isnull=False) | ~Q(state="published"),
                name="mps_media_published_has_date",
            ),
        ]
        indexes = [
            models.Index(fields=["activity", "state", "purpose"], name="mps_media_act_state_purp_idx"),
            models.Index(fields=["occurrence", "state", "purpose"], name="mps_media_occ_state_purp_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.occurrence_id and self.activity_id and self.occurrence.activity_id != self.activity_id:
            errors["occurrence"] = "L’Occurrence doit appartenir à cette Activity."
        if self.asset_id and self.activity_id:
            asset = self.asset
            activity = self.activity
            if asset.owner_space_id:
                if activity.space_id != asset.owner_space_id:
                    errors["asset"] = "L’asset Espace ne correspond pas au propriétaire de l’Activity."
            elif asset.owner_profile_id:
                if activity.space_id or activity.owner_profile_id != asset.owner_profile_id:
                    errors["asset"] = "L’asset Profil ne correspond pas au propriétaire de l’Activity."
            else:
                errors["asset"] = "Un asset sans propriétaire explicite ne peut pas être associé."
        if self.asset_id and self.asset.mime_type not in {"image/jpeg", "image/png"}:
            errors["asset"] = "Seuls les assets image JPEG et PNG sont admis en P2."
        if self.state == PresentationMediaState.PUBLISHED and not self.published_at:
            errors["published_at"] = "La publication doit passer par le service."
        if not (self.alt_text or "").strip():
            errors["alt_text"] = "Un texte alternatif est requis."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self._state.adding and self.state != PresentationMediaState.DRAFT:
            raise ValidationError("Un nouvel usage doit commencer en brouillon.")
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values("state").first()
            if previous and previous["state"] != self.state and not getattr(self, "_allow_state_transition", False):
                raise ValidationError("Utilisez le service de publication ou de retrait.")
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_state_transition = False
        return result
