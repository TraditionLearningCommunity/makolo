import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .models import Promotion, PromotionCode, RedemptionStatus


class PromotionTargeting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.OneToOneField(
        Promotion,
        on_delete=models.CASCADE,
        related_name="canonical_targeting",
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="promotion_targetings",
        null=True,
        blank=True,
    )
    audience = models.ForeignKey(
        "crm.Audience",
        on_delete=models.PROTECT,
        related_name="promotion_targetings",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["activity"], name="promo_target_activity_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.activity_id and self.activity.space_id != self.promotion.organization_id:
            errors["activity"] = "L’Activity doit appartenir au même Espace que la Promotion."
        if self.audience_id and self.audience.organization_id != self.promotion.organization_id:
            errors["audience"] = "L’Audience doit appartenir au même Espace que la Promotion."
        if self.promotion.event_id and self.activity_id:
            event_activity_id = getattr(self.promotion.event, "activity_id", None)
            if event_activity_id and event_activity_id != self.activity_id:
                errors["activity"] = "L’Activity doit correspondre à l’Event historique de la Promotion."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.promotion} — ciblage Commerce"


class PromotionOffer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name="offer_targets")
    offer = models.ForeignKey(
        "commerce.Offer",
        on_delete=models.CASCADE,
        related_name="promotion_targets",
    )
    source = models.CharField(max_length=24, default="canonical")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["promotion", "offer"], name="promotion_offer_unique")
        ]
        indexes = [models.Index(fields=["offer"], name="promotion_offer_offer_idx")]

    def clean(self):
        super().clean()
        if self.offer_id and self.promotion_id:
            if self.offer.activity.space_id != self.promotion.organization_id:
                raise ValidationError({"offer": "L’Offer doit appartenir au même Espace que la Promotion."})
            targeting = getattr(self.promotion, "canonical_targeting", None)
            if targeting and targeting.activity_id and self.offer.activity_id != targeting.activity_id:
                raise ValidationError({"offer": "L’Offer doit appartenir à l’Activity ciblée par la Promotion."})

    def __str__(self):
        return f"{self.promotion} — {self.offer}"


class CommercePromotionRedemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(
        Promotion,
        on_delete=models.PROTECT,
        related_name="commerce_redemptions",
    )
    code = models.ForeignKey(
        PromotionCode,
        on_delete=models.PROTECT,
        related_name="commerce_redemptions",
    )
    commerce_order = models.OneToOneField(
        "commerce.CommerceOrder",
        on_delete=models.CASCADE,
        related_name="promotion_redemption",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="commerce_promotion_redemptions",
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
            models.Index(fields=["promotion", "status", "reserved_at"], name="promo_comm_red_promo_idx"),
            models.Index(fields=["code", "status", "reserved_at"], name="promo_comm_red_code_idx"),
            models.Index(fields=["buyer", "status"], name="promo_comm_red_buyer_idx"),
            models.Index(fields=["customer_email", "status"], name="promo_comm_red_email_idx"),
        ]

    def save(self, *args, **kwargs):
        self.customer_email = (self.customer_email or "").strip().lower()
        self.currency = (self.currency or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code.code} — Commerce {self.commerce_order_id}"
