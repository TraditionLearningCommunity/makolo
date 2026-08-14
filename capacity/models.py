import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CapacityReservationStatus(models.TextChoices):
    HELD = "held", "Retenue"
    COMMITTED = "committed", "Engagée"
    RELEASED = "released", "Libérée"
    EXPIRED = "expired", "Expirée"


ACTIVE_CAPACITY_STATUSES = {
    CapacityReservationStatus.HELD,
    CapacityReservationStatus.COMMITTED,
}


class CapacityPool(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.PROTECT,
        related_name="capacity_pools",
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.PROTECT,
        related_name="capacity_pools",
        null=True,
        blank=True,
    )
    label = models.CharField(max_length=180, blank=True)
    total_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Laisser vide pour une capacité illimitée.",
    )
    is_active = models.BooleanField(default=True)
    source_key = models.CharField(max_length=180, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["activity_id", "occurrence_id", "label", "id"]
        indexes = [
            models.Index(fields=["activity", "is_active"], name="capacity_pool_activity_idx"),
            models.Index(fields=["occurrence", "is_active"], name="capacity_pool_occurrence_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_quantity__isnull=True) | Q(total_quantity__gt=0),
                name="capacity_pool_total_positive",
            )
        ]

    def clean(self):
        super().clean()
        if self.occurrence_id and self.activity_id:
            occurrence_activity_id = self.occurrence.activity_id
            if occurrence_activity_id != self.activity_id:
                raise ValidationError(
                    {"occurrence": "L’Occurrence doit appartenir à la même Activity que le pool de capacité."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_unlimited(self):
        return self.total_quantity is None

    def __str__(self):
        scope = self.occurrence or self.activity
        return self.label or f"Capacité — {scope}"


class CapacityReservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pool = models.ForeignKey(
        CapacityPool,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.PROTECT,
        related_name="capacity_reservations",
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(
        max_length=16,
        choices=CapacityReservationStatus.choices,
        default=CapacityReservationStatus.HELD,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    committed_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    source_key = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["pool", "status"], name="capacity_res_pool_status_idx"),
            models.Index(fields=["journey", "status"], name="cap_res_journey_status_idx"),
            models.Index(fields=["expires_at", "status"], name="capacity_res_expiry_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="capacity_res_quantity_positive"),
            models.UniqueConstraint(
                fields=["pool", "journey", "source_key"],
                condition=~Q(source_key=""),
                name="capacity_res_source_unique",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.pool_id and self.journey_id:
            if self.pool.activity_id != self.journey.activity_id:
                errors["journey"] = "La Démarche appartient à une autre Activity que le pool."
            if self.pool.occurrence_id and self.journey.occurrence_id != self.pool.occurrence_id:
                errors["journey"] = "La Démarche doit cibler l’Occurrence du pool."
        if self.created_at and self.status == CapacityReservationStatus.HELD and self.expires_at and self.expires_at <= self.created_at:
            errors["expires_at"] = "L’expiration d’un hold doit être postérieure à sa création."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = CapacityReservation.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError(
                    {"status": "Utilisez les services Capacity pour changer l’état d’une réservation."}
                )
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    @property
    def is_active_hold(self):
        return bool(
            self.status == CapacityReservationStatus.HELD
            and (self.expires_at is None or self.expires_at > timezone.now())
        )

    def __str__(self):
        return f"{self.pool} — {self.quantity} — {self.get_status_display()}"