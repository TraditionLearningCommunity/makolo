import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class PlacementPlan(models.Model):
    """Occurrence-scoped dimension of placement, such as seating or transport."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.CASCADE,
        related_name="placement_plans",
    )
    key = models.CharField(max_length=80)
    label = models.CharField(max_length=180)
    required = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "operations"
        ordering = ["occurrence_id", "label", "id"]
        constraints = [
            models.UniqueConstraint(fields=["occurrence", "key"], name="ops_place_plan_key_uq"),
        ]
        indexes = [
            models.Index(fields=["occurrence", "active"], name="ops_place_plan_occ_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.key = (self.key or "").strip()
        self.label = (self.label or "").strip()
        if not self.key:
            errors["key"] = "La clé du plan de placement est obligatoire."
        if not self.label:
            errors["label"] = "Le libellé du plan de placement est obligatoire."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.occurrence_id} — {self.label}"


class PlacementUnit(models.Model):
    """Logical placement destination. It is neither Capacity nor Geography."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(PlacementPlan, on_delete=models.CASCADE, related_name="units")
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    key = models.CharField(max_length=80)
    label = models.CharField(max_length=180)
    kind = models.CharField(max_length=48, blank=True)
    position = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    exclusive = models.BooleanField(
        default=False,
        help_text="Politique d’exclusivité du placement; ne représente pas une capacité.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "operations"
        ordering = ["plan_id", "position", "label", "id"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "key"], name="ops_place_unit_key_uq"),
        ]
        indexes = [
            models.Index(fields=["plan", "active", "position"], name="ops_place_unit_plan_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.key = (self.key or "").strip()
        self.label = (self.label or "").strip()
        self.kind = (self.kind or "").strip()
        if not self.key:
            errors["key"] = "La clé de l’unité de placement est obligatoire."
        if not self.label:
            errors["label"] = "Le libellé de l’unité de placement est obligatoire."
        if self.parent_id:
            if self.parent_id == self.pk:
                errors["parent"] = "Une unité ne peut pas être son propre parent."
            elif self.plan_id and self.parent.plan_id != self.plan_id:
                errors["parent"] = "Le parent doit appartenir au même plan de placement."
            else:
                seen = {self.pk}
                ancestor = self.parent
                while ancestor is not None:
                    if ancestor.pk in seen:
                        errors["parent"] = "La hiérarchie des unités ne peut pas contenir de cycle."
                        break
                    seen.add(ancestor.pk)
                    if ancestor.plan_id != self.plan_id:
                        errors["parent"] = "Toute la hiérarchie doit appartenir au même plan de placement."
                        break
                    ancestor = ancestor.parent
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.plan.label} — {self.label}"


class PlacementAssignment(models.Model):
    """Append-and-close assignment of exactly one beneficiary to one unit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(PlacementPlan, on_delete=models.PROTECT, related_name="assignments")
    unit = models.ForeignKey(PlacementUnit, on_delete=models.PROTECT, related_name="assignments")
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="placement_assignments_as_beneficiary",
        null=True,
        blank=True,
    )
    external_beneficiary = models.ForeignKey(
        "journeys.ExternalBeneficiary",
        on_delete=models.PROTECT,
        related_name="placement_assignments",
        null=True,
        blank=True,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="placement_assignments_made",
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "operations"
        ordering = ["-assigned_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(profile__isnull=False) & models.Q(external_beneficiary__isnull=True))
                | (models.Q(profile__isnull=True) & models.Q(external_beneficiary__isnull=False)),
                name="ops_place_one_subject_ck",
            ),
            models.UniqueConstraint(
                fields=["plan", "profile"],
                condition=models.Q(ended_at__isnull=True, profile__isnull=False),
                name="ops_place_active_profile_uq",
            ),
            models.UniqueConstraint(
                fields=["plan", "external_beneficiary"],
                condition=models.Q(ended_at__isnull=True, external_beneficiary__isnull=False),
                name="ops_place_active_ext_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F("assigned_at")),
                name="ops_place_end_after_start_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["plan", "ended_at"], name="ops_place_asg_plan_idx"),
            models.Index(fields=["unit", "ended_at"], name="ops_place_asg_unit_idx"),
            models.Index(fields=["profile", "assigned_at"], name="ops_place_asg_profile_idx"),
            models.Index(fields=["external_beneficiary", "assigned_at"], name="ops_place_asg_ext_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if bool(self.profile_id) == bool(self.external_beneficiary_id):
            errors["profile"] = "Le placement doit avoir exactement un bénéficiaire, Profile ou externe."
        if self.unit_id and self.plan_id and self.unit.plan_id != self.plan_id:
            errors["unit"] = "L’unité doit appartenir au plan de placement sélectionné."
        if self.ended_at and self.assigned_at and self.ended_at < self.assigned_at:
            errors["ended_at"] = "La fin d’une affectation ne peut pas précéder son début."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.ended_at is None

    @property
    def beneficiary_display_name(self):
        if self.profile_id:
            full_name = self.profile.get_full_name().strip()
            return full_name or self.profile.username
        return self.external_beneficiary.display_name if self.external_beneficiary_id else ""

    def __str__(self):
        return f"{self.beneficiary_display_name} — {self.unit.label}"
