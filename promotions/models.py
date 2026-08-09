import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


class DiscountType(models.TextChoices):
    PERCENT = "percent", "Pourcentage"
    FIXED = "fixed", "Montant fixe"


class RedemptionStatus(models.TextChoices):
    RESERVED = "reserved", "Réservée"
    CONFIRMED = "confirmed", "Confirmée"
    REVERSED = "reversed", "Annulée"


class Promotion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="promotions",
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="promotions",
        null=True,
        blank=True,
        help_text="Laisser vide pour une offre valable sur les événements de l'organisation.",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices)
    discount_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    max_discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Plafond facultatif pour une remise en pourcentage.",
    )
    min_order_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(max_length=3, blank=True)
    eligible_ticket_types = models.ManyToManyField(
        "tickets.TicketType",
        blank=True,
        related_name="eligible_promotions",
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    max_redemptions_per_customer = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_promotions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="promotion_org_name_unique",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "is_active"], name="promotion_org_active_idx"),
            models.Index(fields=["event", "is_active"], name="promotion_event_active_idx"),
        ]

    def clean(self):
        self.currency = (self.currency or "").strip().upper()
        super().clean()
        errors = {}
        if self.event_id and self.event.organization_id != self.organization_id:
            errors["event"] = "L'événement doit appartenir à la même organisation."
        if self.discount_type == DiscountType.PERCENT and self.discount_value > 100:
            errors["discount_value"] = "Une remise en pourcentage ne peut pas dépasser 100 %."
        if self.discount_type == DiscountType.FIXED and not self.currency:
            errors["currency"] = "Une remise fixe nécessite une devise."
        if self.min_order_amount and not self.currency:
            errors["currency"] = "Un minimum de commande nécessite une devise."
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "La date de fin doit être postérieure à la date de début."
        if self.max_redemptions is not None and self.max_redemptions < 1:
            errors["max_redemptions"] = "Le quota global doit être supérieur à zéro."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization} — {self.name}"


class PromotionCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name="codes")
    code = models.CharField(
        max_length=40,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,39}$",
                message="Le code doit contenir 3 à 40 caractères : lettres, chiffres, _ ou -.",
            )
        ],
    )
    label = models.CharField(max_length=120, blank=True)
    crm_campaign = models.ForeignKey(
        "crm.CommunicationCampaign",
        on_delete=models.SET_NULL,
        related_name="promotion_codes",
        null=True,
        blank=True,
        help_text="Campagne CRM associée pour mesurer l'usage du code, sans fabriquer une attribution de clic.",
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    is_private = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_promotion_codes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["promotion", "code"]
        indexes = [
            models.Index(fields=["promotion", "is_active"], name="promo_code_promo_active_idx"),
            models.Index(fields=["crm_campaign", "is_active"], name="promo_code_campaign_idx"),
        ]

    def clean(self):
        self.code = (self.code or "").strip().upper()
        super().clean()
        errors = {}
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "La date de fin du code doit être postérieure à sa date de début."
        if self.max_redemptions is not None and self.max_redemptions < 1:
            errors["max_redemptions"] = "Le quota du code doit être supérieur à zéro."
        if self.crm_campaign_id:
            if self.crm_campaign.organization_id != self.promotion.organization_id:
                errors["crm_campaign"] = "La campagne CRM doit appartenir à la même organisation."
            if self.promotion.event_id and self.crm_campaign.event_id and self.crm_campaign.event_id != self.promotion.event_id:
                errors["crm_campaign"] = "La campagne CRM concerne un autre événement."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class PromotionRedemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(Promotion, on_delete=models.PROTECT, related_name="redemptions")
    code = models.ForeignKey(PromotionCode, on_delete=models.PROTECT, related_name="redemptions")
    order = models.OneToOneField(
        "tickets.TicketOrder",
        on_delete=models.CASCADE,
        related_name="promotion_redemption",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="promotion_redemptions",
        null=True,
        blank=True,
    )
    customer_email = models.EmailField()
    status = models.CharField(
        max_length=16,
        choices=RedemptionStatus.choices,
        default=RedemptionStatus.RESERVED,
    )
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    eligible_amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    final_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    reserved_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-reserved_at"]
        indexes = [
            models.Index(fields=["promotion", "status", "reserved_at"], name="promo_redemption_offer_idx"),
            models.Index(fields=["code", "status", "reserved_at"], name="promo_redemption_code_idx"),
            models.Index(fields=["buyer", "status"], name="promo_redemption_buyer_idx"),
            models.Index(fields=["customer_email", "status"], name="promo_redemption_email_idx"),
        ]

    def save(self, *args, **kwargs):
        self.customer_email = (self.customer_email or "").strip().lower()
        self.currency = (self.currency or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code.code} — {self.order.reference} — {self.status}"
