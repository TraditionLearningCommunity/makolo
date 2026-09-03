import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CheckpointStatus(models.TextChoices):
    PLANNED = "planned", "Planifié"
    OPEN = "open", "Ouvert"
    PAUSED = "paused", "En pause"
    CLOSED = "closed", "Fermé"


class OccurrenceCheckpoint(models.Model):
    """Occurrence-scoped operational point. It is not Geography, Access, Journey, Scanner or Placement."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.CASCADE,
        related_name="checkpoints",
    )
    key = models.CharField(max_length=80)
    label = models.CharField(max_length=180)
    description = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)
    required = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=CheckpointStatus.choices, default=CheckpointStatus.PLANNED)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "operations"
        ordering = ["occurrence_id", "position", "label", "id"]
        constraints = [
            models.UniqueConstraint(fields=["occurrence", "key"], name="ops_checkpoint_key_uq"),
        ]
        indexes = [
            models.Index(fields=["occurrence", "active", "position"], name="ops_checkpoint_occ_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.key = (self.key or "").strip()
        self.label = (self.label or "").strip()
        self.description = (self.description or "").strip()
        if not self.key:
            errors["key"] = "La clé du checkpoint est obligatoire."
        if not self.label:
            errors["label"] = "Le libellé du checkpoint est obligatoire."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.occurrence_id} — {self.label}"


class CheckpointAssignment(models.Model):
    """Operational responsibility only; never grants server authority."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checkpoint = models.ForeignKey(OccurrenceCheckpoint, on_delete=models.PROTECT, related_name="assignments")
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="checkpoint_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="checkpoint_assignments_made",
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "operations"
        ordering = ["-assigned_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["checkpoint", "profile"],
                condition=Q(ended_at__isnull=True),
                name="ops_checkpoint_active_asg_uq",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gte=models.F("assigned_at")),
                name="ops_checkpoint_asg_time_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["checkpoint", "ended_at"], name="ops_checkpoint_asg_idx"),
            models.Index(fields=["profile", "ended_at"], name="ops_checkpoint_prof_idx"),
        ]

    def clean(self):
        super().clean()
        if self.ended_at and self.assigned_at and self.ended_at < self.assigned_at:
            raise ValidationError({"ended_at": "La fin d’affectation ne peut pas précéder son début."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.ended_at is None


class CheckpointObservation(models.Model):
    """Immutable successful operational passage through a checkpoint."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checkpoint = models.ForeignKey(OccurrenceCheckpoint, on_delete=models.PROTECT, related_name="observations")
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="checkpoint_observations_as_beneficiary",
        null=True,
        blank=True,
    )
    external_beneficiary = models.ForeignKey(
        "journeys.ExternalBeneficiary",
        on_delete=models.PROTECT,
        related_name="checkpoint_observations",
        null=True,
        blank=True,
    )
    observed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="checkpoint_observations_made",
    )
    observed_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=80, blank=True)
    client_reference = models.CharField(max_length=64, blank=True)
    access_use = models.ForeignKey(
        "access.AccessUse",
        on_delete=models.PROTECT,
        related_name="checkpoint_observations",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "operations"
        ordering = ["-observed_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(profile__isnull=False) & Q(external_beneficiary__isnull=True))
                | (Q(profile__isnull=True) & Q(external_beneficiary__isnull=False)),
                name="ops_checkpoint_obs_subject_ck",
            ),
            models.UniqueConstraint(
                fields=["checkpoint", "profile"],
                condition=Q(profile__isnull=False),
                name="ops_checkpoint_obs_profile_uq",
            ),
            models.UniqueConstraint(
                fields=["checkpoint", "external_beneficiary"],
                condition=Q(external_beneficiary__isnull=False),
                name="ops_checkpoint_obs_ext_uq",
            ),
            models.UniqueConstraint(
                fields=["source", "client_reference"],
                condition=~Q(source="") & ~Q(client_reference=""),
                name="ops_checkpoint_obs_client_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["checkpoint", "observed_at"], name="ops_checkpoint_obs_idx"),
            models.Index(fields=["profile", "observed_at"], name="ops_checkpoint_obs_prof_idx"),
            models.Index(fields=["external_beneficiary", "observed_at"], name="ops_checkpoint_obs_ext_idx"),
            models.Index(fields=["access_use"], name="ops_checkpoint_obs_access_idx"),
        ]

    def clean(self):
        super().clean()
        if bool(self.profile_id) == bool(self.external_beneficiary_id):
            raise ValidationError({"profile": "L’observation doit viser exactement un bénéficiaire, Profile ou externe."})

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Une observation de checkpoint est immuable.")
        self.full_clean()
        return super().save(*args, **kwargs)
