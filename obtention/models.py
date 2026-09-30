import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class ObtentionModeCode(models.TextChoices):
    BUY = "buy", "Achat"
    RENT = "rent", "Location"
    BORROW = "borrow", "Emprunt"
    RECEIVE = "receive", "Réception / attribution"
    EXCHANGE = "exchange", "Échange"
    OTHER = "other", "Autre"


class FulfillmentTargetRule(models.TextChoices):
    ALL = "all", "Toutes les cibles"
    ANY = "any", "Au moins une cible"
    AT_LEAST_N = "at_least_n", "Au moins N cibles"


class ObtentionDetails(models.Model):
    """Facts that are irreducibly specific to one Obtention Activity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.OneToOneField(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="obtention_details",
    )
    result_label = models.CharField(
        max_length=220,
        help_text="Résultat réel permettant de dire que l'obtention est accomplie.",
    )
    target_rule = models.CharField(
        max_length=16,
        choices=FulfillmentTargetRule.choices,
        default=FulfillmentTargetRule.ALL,
    )
    minimum_targets = models.PositiveSmallIntegerField(null=True, blank=True)
    beneficiary_confirmation_required = models.BooleanField(default=True)
    operator_confirmation_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["activity__title", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(minimum_targets__isnull=True) | Q(minimum_targets__gt=0),
                name="obtention_min_targets_positive",
            ),
        ]

    def clean(self):
        super().clean()
        self.result_label = (self.result_label or "").strip()
        errors = {}
        if not self.result_label:
            errors["result_label"] = "Définissez le résultat réel qui signifie « obtenu »."
        if self.target_rule == FulfillmentTargetRule.AT_LEAST_N:
            if not self.minimum_targets or self.minimum_targets < 1:
                errors["minimum_targets"] = "La règle « au moins N » exige une valeur strictement positive."
        elif self.minimum_targets is not None:
            errors["minimum_targets"] = "Le nombre minimal ne s'applique qu'à la règle « au moins N »."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.result_label = (self.result_label or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Obtention — {self.activity}"


class ObtentionTarget(models.Model):
    """What must actually be obtained; intentionally distinct from Commerce Offer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obtention = models.ForeignKey(
        ObtentionDetails,
        on_delete=models.CASCADE,
        related_name="targets",
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit = models.CharField(max_length=40, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="obtention_target_quantity_positive"),
        ]
        indexes = [
            models.Index(fields=["obtention", "position"], name="obtention_target_order_idx"),
        ]

    def clean(self):
        super().clean()
        self.title = (self.title or "").strip()
        self.description = (self.description or "").strip()
        self.unit = (self.unit or "").strip()
        errors = {}
        if not self.title:
            errors["title"] = "La cible doit avoir un intitulé."
        if self.quantity is None or self.quantity <= 0:
            errors["quantity"] = "La quantité cible doit être strictement positive."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.title = (self.title or "").strip()
        self.description = (self.description or "").strip()
        self.unit = (self.unit or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        suffix = f" {self.unit}" if self.unit else ""
        return f"{self.quantity:g}{suffix} — {self.title}"


class ObtentionMode(models.Model):
    """One admissible relation of obtaining for an Activity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obtention = models.ForeignKey(
        ObtentionDetails,
        on_delete=models.CASCADE,
        related_name="modes",
    )
    code = models.CharField(max_length=16, choices=ObtentionModeCode.choices)
    label = models.CharField(
        max_length=120,
        blank=True,
        help_text="Libellé métier optionnel lorsque le contexte exige plus de précision.",
    )
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["obtention", "code"], name="obtention_mode_unique"),
        ]

    def clean(self):
        super().clean()
        self.label = (self.label or "").strip()

    def save(self, *args, **kwargs):
        self.label = (self.label or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.label or self.get_code_display()


class ObtentionModeSelection(models.Model):
    """The mode chosen for one canonical Journey; it is not a Journey status."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.OneToOneField(
        "journeys.Journey",
        on_delete=models.CASCADE,
        related_name="obtention_mode_selection",
    )
    mode = models.ForeignKey(
        ObtentionMode,
        on_delete=models.PROTECT,
        related_name="selections",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def clean(self):
        super().clean()
        if self.journey_id and self.mode_id:
            if self.journey.activity_id != self.mode.obtention.activity_id:
                raise ValidationError({"mode": "Le mode doit appartenir à l'Obtention de cette Journey."})

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = ObtentionModeSelection.objects.filter(pk=self.pk).values(
                "journey_id", "mode_id"
            ).first()
            if previous and (
                previous["journey_id"] != self.journey_id
                or previous["mode_id"] != self.mode_id
            ):
                raise ValidationError("Le mode choisi d'une Journey est immuable.")
        self.full_clean()
        return super().save(*args, **kwargs)


class ObtentionTargetReceipt(models.Model):
    """Observed target quantity and confirmations for one Journey.

    This records the vertical fact « actually obtained », without duplicating
    Payment, Order, Journey status, Proof or Readiness.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.CASCADE,
        related_name="obtention_target_receipts",
    )
    target = models.ForeignKey(
        ObtentionTarget,
        on_delete=models.PROTECT,
        related_name="receipts",
    )
    received_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    beneficiary_confirmed_at = models.DateTimeField(null=True, blank=True)
    operator_confirmed_at = models.DateTimeField(null=True, blank=True)
    operator_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="confirmed_obtention_receipts",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_obtention_receipts",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target__position", "target_id"]
        constraints = [
            models.UniqueConstraint(fields=["journey", "target"], name="obtention_receipt_target_unique"),
            models.CheckConstraint(condition=Q(received_quantity__gte=0), name="obtention_receipt_quantity_nonnegative"),
        ]
        indexes = [
            models.Index(fields=["journey", "target"], name="obtention_receipt_journey_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.received_quantity is None or self.received_quantity < 0:
            errors["received_quantity"] = "La quantité reçue ne peut pas être négative."
        if self.journey_id and self.target_id:
            if self.journey.activity_id != self.target.obtention.activity_id:
                errors["target"] = "La cible doit appartenir à l'Obtention de cette Journey."
        if self.operator_confirmed_at and not self.operator_confirmed_by_id:
            errors["operator_confirmed_by"] = "Une confirmation du porteur doit identifier son auteur."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = ObtentionTargetReceipt.objects.filter(pk=self.pk).values(
                "journey_id", "target_id"
            ).first()
            if previous and (
                previous["journey_id"] != self.journey_id
                or previous["target_id"] != self.target_id
            ):
                raise ValidationError("L'identité d'un constat d'obtention est immuable.")
        self.full_clean()
        return super().save(*args, **kwargs)
