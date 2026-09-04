import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ActivityBookmark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity_bookmarks")
    activity = models.ForeignKey("activities.Activity", on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "activity"], name="disc_bm_user_activity_uq")]
        indexes = [models.Index(fields=["user", "created_at"], name="disc_bm_user_created_idx"), models.Index(fields=["activity", "created_at"], name="disc_bm_activity_created_idx")]

    def __str__(self):
        return f"{self.user} — {self.activity}"


class _LegacyEventBookmarkManager:
    @staticmethod
    def _translate(kwargs):
        values = dict(kwargs)
        event = values.pop("event", None)
        event_id = values.pop("event_id", None)
        if event is not None:
            values["activity_id"] = event.activity_id
        elif event_id is not None:
            values["activity__event_vertical_id"] = event_id
        return values

    def filter(self, *args, **kwargs):
        return ActivityBookmark.objects.filter(*args, **self._translate(kwargs))


class EventBookmark:
    objects = _LegacyEventBookmarkManager()


class DiscoveryWatchStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PAUSED = "paused", "En pause"


class DiscoveryWatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="discovery_watches")
    name = models.CharField(max_length=140)
    status = models.CharField(max_length=16, choices=DiscoveryWatchStatus.choices, default=DiscoveryWatchStatus.ACTIVE)
    criteria = models.JSONField(default=dict)
    dossier = models.ForeignKey("objectives.Dossier", on_delete=models.SET_NULL, related_name="discovery_watches", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "id"]
        indexes = [models.Index(fields=["owner", "status", "updated_at"], name="disc_watch_owner_state_idx")]

    def clean(self):
        super().clean()
        from .watches import normalize_watch_criteria
        self.name = (self.name or "").strip()
        errors = {}
        if not self.name:
            errors["name"] = "Le nom de la Veille est obligatoire."
        try:
            self.criteria = normalize_watch_criteria(self.criteria)
        except ValidationError as exc:
            errors["criteria"] = exc.messages
        if self.dossier_id:
            if self.owner_id is None:
                errors["owner"] = "Le propriétaire est requis avant de rattacher un Dossier."
            elif self.dossier.owner_profile_id != self.owner_id or self.dossier.owning_space_id is not None:
                errors["dossier"] = "Une Veille ne peut être liée qu’à un Dossier personnel du même propriétaire."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.owner} — {self.name}"
