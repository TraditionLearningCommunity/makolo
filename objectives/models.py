import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


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
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_dossiers")
    owner_profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_dossiers", null=True, blank=True)
    owning_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="dossiers", null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    lifecycle = models.CharField(max_length=16, choices=DossierLifecycle.choices, default=DossierLifecycle.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "id"]
        constraints = [models.CheckConstraint(condition=(Q(owner_profile__isnull=False) & Q(owning_space__isnull=True)) | (Q(owner_profile__isnull=True) & Q(owning_space__isnull=False)), name="dossier_exactly_one_owner_context")]
        indexes = [models.Index(fields=["owner_profile", "lifecycle"], name="dossier_owner_lifecycle_idx"), models.Index(fields=["owning_space", "lifecycle"], name="dossier_space_lifecycle_idx")]

    def clean(self):
        super().clean()
        self.title = (self.title or "").strip(); self.description = (self.description or "").strip(); errors = {}
        if not self.title: errors["title"] = "L’objectif du Dossier est obligatoire."
        if bool(self.owner_profile_id) == bool(self.owning_space_id): errors["owner_profile"] = "Un Dossier doit être porté par exactement un Profile ou un Espace."
        if errors: raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_lifecycle_transition", False):
            previous = Dossier.objects.filter(pk=self.pk).values_list("lifecycle", flat=True).first()
            if previous is not None and previous != self.lifecycle: raise ValidationError({"lifecycle": "Utilisez le service de transition Dossier pour changer cet état."})
        result = super().save(*args, **kwargs); self._allow_lifecycle_transition = False; return result


class DossierAssignmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REMOVED = "removed", "Retirée"


class DossierAssignment(models.Model):
    """Operational responsibility for a Dossier. It never grants authority."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="assignments")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dossier_assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dossier_assignments_created")
    assigned_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=16, choices=DossierAssignmentStatus.choices, default=DossierAssignmentStatus.ACTIVE)
    removed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dossier_assignments_removed", null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["assigned_at", "id"]
        constraints = [models.UniqueConstraint(fields=["dossier", "assignee"], condition=Q(status=DossierAssignmentStatus.ACTIVE), name="dossier_assignment_active_unique")]
        indexes = [models.Index(fields=["dossier", "status"], name="dossier_assign_status_idx"), models.Index(fields=["assignee", "status"], name="dossier_assignee_status_idx")]

    def clean(self):
        super().clean()
        if self.status == DossierAssignmentStatus.REMOVED and not self.removed_at: raise ValidationError({"removed_at": "Une responsabilité retirée doit conserver sa date de retrait."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = DossierAssignment.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status: raise ValidationError({"status": "Utilisez le service de responsabilité Dossier."})
        result = super().save(*args, **kwargs); self._allow_status_transition = False; return result


class DossierJourneyLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="journey_links")
    journey = models.ForeignKey("journeys.Journey", on_delete=models.PROTECT, related_name="dossier_links")
    linked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dossier_journey_links_created")
    linked_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    unlinked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dossier_journey_links_removed", null=True, blank=True)
    unlinked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["linked_at", "id"]
        constraints = [models.UniqueConstraint(fields=["dossier", "journey"], condition=Q(is_active=True), name="dossier_journey_one_active_link")]
        indexes = [models.Index(fields=["dossier", "is_active"], name="dossier_link_active_idx"), models.Index(fields=["journey", "is_active"], name="journey_dossier_active_idx")]


class DossierJourneyDependencyState(models.TextChoices):
    ACTIVE = "active", "Active"
    WAIVED = "waived", "Levée"
    REMOVED = "removed", "Retirée"


class DossierJourneyDependency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="journey_dependencies")
    dependent_link = models.ForeignKey(DossierJourneyLink, on_delete=models.PROTECT, related_name="dependencies_as_dependent")
    required_link = models.ForeignKey(DossierJourneyLink, on_delete=models.PROTECT, related_name="dependencies_as_required")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dossier_journey_dependencies_created")
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=16, choices=DossierJourneyDependencyState.choices, default=DossierJourneyDependencyState.ACTIVE)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dossier_journey_dependencies_closed", null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    waiver_reason = models.CharField(max_length=280, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.CheckConstraint(condition=~Q(dependent_link=F("required_link")), name="dossier_dependency_distinct_links"), models.UniqueConstraint(fields=["dossier", "dependent_link", "required_link"], condition=Q(state=DossierJourneyDependencyState.ACTIVE), name="dossier_dependency_one_active_pair")]
        indexes = [models.Index(fields=["dossier", "state"], name="dossier_dependency_state_idx"), models.Index(fields=["dependent_link", "state"], name="dossier_dep_dependent_idx"), models.Index(fields=["required_link", "state"], name="dossier_dep_required_idx")]

    def clean(self):
        super().clean(); errors = {}
        if self.dependent_link_id and self.required_link_id and self.dependent_link_id == self.required_link_id: errors["required_link"] = "Une démarche ne peut pas dépendre d’elle-même."
        if self.dossier_id and self.dependent_link_id and self.dependent_link.dossier_id != self.dossier_id: errors["dependent_link"] = "La démarche dépendante doit appartenir à ce Dossier."
        if self.dossier_id and self.required_link_id and self.required_link.dossier_id != self.dossier_id: errors["required_link"] = "La démarche requise doit appartenir à ce Dossier."
        if self.state == DossierJourneyDependencyState.ACTIVE:
            if self.dependent_link_id and not self.dependent_link.is_active: errors["dependent_link"] = "La démarche dépendante doit être activement liée au Dossier."
            if self.required_link_id and not self.required_link.is_active: errors["required_link"] = "La démarche requise doit être activement liée au Dossier."
        if self.state == DossierJourneyDependencyState.WAIVED and not (self.waiver_reason or "").strip(): errors["waiver_reason"] = "Une raison est requise pour lever ce prérequis."
        if errors: raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean(); return super().save(*args, **kwargs)
