import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class DossierLifecycle(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    ACTIVE = "active", "Actif"
    COMPLETED = "completed", "Terminé"
    CANCELLED = "cancelled", "Annulé"
    ARCHIVED = "archived", "Archivé"


class Dossier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_dossiers",
    )
    owner_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_dossiers",
        null=True,
        blank=True,
    )
    owning_space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="dossiers",
        null=True,
        blank=True,
    )
    deadline = models.DateField(null=True, blank=True)
    lifecycle = models.CharField(
        max_length=16,
        choices=DossierLifecycle.choices,
        default=DossierLifecycle.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(owner_profile__isnull=False) & Q(owning_space__isnull=True))
                | (Q(owner_profile__isnull=True) & Q(owning_space__isnull=False)),
                name="dossier_exactly_one_owner_context",
            )
        ]
        indexes = [
            models.Index(fields=["owner_profile", "lifecycle"], name="dossier_owner_lifecycle_idx"),
            models.Index(fields=["owning_space", "lifecycle"], name="dossier_space_lifecycle_idx"),
        ]

    def clean(self):
        super().clean()
        self.title = (self.title or "").strip()
        self.description = (self.description or "").strip()
        errors = {}
        if not self.title:
            errors["title"] = "L’objectif du Dossier est obligatoire."
        if bool(self.owner_profile_id) == bool(self.owning_space_id):
            errors["owner_profile"] = "Un Dossier doit être porté par exactement un Profile ou un Espace."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_lifecycle_transition", False):
            previous = Dossier.objects.filter(pk=self.pk).values_list("lifecycle", flat=True).first()
            if previous is not None and previous != self.lifecycle:
                raise ValidationError(
                    {"lifecycle": "Utilisez le service de transition Dossier pour changer cet état."}
                )
        result = super().save(*args, **kwargs)
        self._allow_lifecycle_transition = False
        return result


class DossierJourneyLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="journey_links")
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.PROTECT,
        related_name="dossier_links",
    )
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dossier_journey_links_created",
    )
    linked_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    unlinked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dossier_journey_links_removed",
        null=True,
        blank=True,
    )
    unlinked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["linked_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["dossier", "journey"],
                condition=Q(is_active=True),
                name="dossier_journey_one_active_link",
            )
        ]
        indexes = [
            models.Index(fields=["dossier", "is_active"], name="dossier_link_active_idx"),
            models.Index(fields=["journey", "is_active"], name="journey_dossier_active_idx"),
        ]
