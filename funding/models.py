import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class FundingDetails(models.Model):
    """Financing-specific facts for one generic Activity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.OneToOneField(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="funding_details",
    )
    currency = models.CharField(max_length=3, default="USD")
    target_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    minimum_contribution = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    maximum_contribution = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["activity__title", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(target_amount__isnull=True) | Q(target_amount__gt=0),
                name="funding_target_positive",
            ),
            models.CheckConstraint(
                condition=Q(minimum_contribution__isnull=True) | Q(minimum_contribution__gt=0),
                name="funding_min_positive",
            ),
            models.CheckConstraint(
                condition=Q(maximum_contribution__isnull=True) | Q(maximum_contribution__gt=0),
                name="funding_max_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(minimum_contribution__isnull=True)
                    | Q(maximum_contribution__isnull=True)
                    | Q(maximum_contribution__gte=models.F("minimum_contribution"))
                ),
                name="funding_min_lte_max",
            ),
            models.CheckConstraint(
                condition=Q(closes_at__isnull=True) | Q(opens_at__isnull=True) | Q(closes_at__gte=models.F("opens_at")),
                name="funding_window_valid",
            ),
        ]

    def clean(self):
        super().clean()
        self.currency = (self.currency or "").strip().upper()
        errors = {}
        if len(self.currency) != 3 or not self.currency.isalpha():
            errors["currency"] = "La devise doit être un code ISO 4217 de trois lettres."
        if self.target_amount is not None and self.target_amount <= 0:
            errors["target_amount"] = "L’objectif, lorsqu’il existe, doit être strictement positif."
        if self.minimum_contribution is not None and self.minimum_contribution <= 0:
            errors["minimum_contribution"] = "Le minimum doit être strictement positif."
        if self.maximum_contribution is not None and self.maximum_contribution <= 0:
            errors["maximum_contribution"] = "Le maximum doit être strictement positif."
        if (
            self.minimum_contribution is not None
            and self.maximum_contribution is not None
            and self.maximum_contribution < self.minimum_contribution
        ):
            errors["maximum_contribution"] = "Le maximum ne peut pas être inférieur au minimum."
        if self.opens_at and self.closes_at and self.closes_at < self.opens_at:
            errors["closes_at"] = "La clôture doit être postérieure à l’ouverture."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "").strip().upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Financement — {self.activity}"


class FundingContribution(models.Model):
    """Voluntary financing intent; Payment remains the execution truth."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funding = models.ForeignKey(FundingDetails, on_delete=models.PROTECT, related_name="contributions")
    contributor_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="funding_contributions",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3)
    client_reference = models.CharField(max_length=120, blank=True)
    payment_obligation = models.OneToOneField(
        "payments.PaymentObligation",
        on_delete=models.PROTECT,
        related_name="funding_contribution",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["funding", "created_at"], name="funding_contrib_time_idx"),
            models.Index(fields=["contributor_profile", "created_at"], name="funding_profile_time_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="funding_contribution_positive"),
            models.UniqueConstraint(
                fields=["funding", "contributor_profile", "client_reference"],
                condition=~Q(client_reference=""),
                name="funding_contribution_client_unique",
            ),
        ]

    def clean(self):
        super().clean()
        self.currency = (self.currency or "").strip().upper()
        self.client_reference = (self.client_reference or "").strip()
        errors = {}
        if self.amount is None or self.amount <= 0:
            errors["amount"] = "Le montant de la contribution doit être strictement positif."
        if self.funding_id:
            if self.currency != self.funding.currency:
                errors["currency"] = "La contribution doit utiliser la devise du financement."
            if self.amount is not None:
                minimum = self.funding.minimum_contribution
                maximum = self.funding.maximum_contribution
                if minimum is not None and self.amount < minimum:
                    errors["amount"] = f"La contribution minimale est de {minimum} {self.currency}."
                if maximum is not None and self.amount > maximum:
                    errors["amount"] = f"La contribution maximale est de {maximum} {self.currency}."
        if self.payment_obligation_id:
            obligation = self.payment_obligation
            if obligation.payer_profile_id != self.contributor_profile_id:
                errors["payment_obligation"] = "L’obligation doit appartenir au contributeur."
            if obligation.amount != self.amount or obligation.currency != self.currency:
                errors["payment_obligation"] = "L’obligation doit conserver le montant et la devise de la contribution."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "").strip().upper()
        self.client_reference = (self.client_reference or "").strip()
        if self.pk and not self._state.adding:
            previous = FundingContribution.objects.filter(pk=self.pk).values(
                "funding_id",
                "contributor_profile_id",
                "amount",
                "currency",
                "client_reference",
                "payment_obligation_id",
            ).first()
            if previous:
                immutable = {
                    "funding_id": self.funding_id,
                    "contributor_profile_id": self.contributor_profile_id,
                    "amount": self.amount,
                    "currency": self.currency,
                    "client_reference": self.client_reference,
                }
                if any(previous[name] != value for name, value in immutable.items()):
                    raise ValidationError("Une contribution créée est immuable.")
                obligation_changed = previous["payment_obligation_id"] != self.payment_obligation_id
                if obligation_changed and not (
                    getattr(self, "_allow_payment_link", False)
                    and previous["payment_obligation_id"] is None
                    and self.payment_obligation_id is not None
                ):
                    raise ValidationError("Utilisez le service Financement pour rattacher le paiement.")
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_payment_link = False
        return result

    def delete(self, *args, **kwargs):
        if self.pk and FundingContribution.objects.filter(pk=self.pk).exists():
            raise ValidationError("Une contribution auditée ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.amount} {self.currency} — {self.funding.activity}"
