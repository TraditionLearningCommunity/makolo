import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class PaymentMode(models.TextChoices):
    NONE = "none", "Aucun paiement"
    UPFRONT = "upfront", "Paiement avant confirmation"
    AFTER_APPROVAL = "after_approval", "Paiement après validation"
    ON_SITE = "on_site", "Paiement sur place"
    LATER = "later", "Paiement différé"


class OfferStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archivée"


class CommerceOrderStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PENDING = "pending", "En attente"
    CONFIRMED = "confirmed", "Confirmée"
    CANCELLED = "cancelled", "Annulée"
    EXPIRED = "expired", "Expirée"
    REFUNDED = "refunded", "Remboursée"


class Offer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.PROTECT,
        related_name="offers",
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.PROTECT,
        related_name="offers",
        null=True,
        blank=True,
    )
    capacity_pool = models.ForeignKey(
        "capacity.CapacityPool",
        on_delete=models.PROTECT,
        related_name="offers",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(max_length=3, default="USD")
    payment_mode = models.CharField(
        max_length=24,
        choices=PaymentMode.choices,
        default=PaymentMode.NONE,
        help_text="Mode par défaut et compatibilité legacy. Les choix supplémentaires vivent dans payment_options.",
    )
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)
    min_quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    max_quantity = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=16, choices=OfferStatus.choices, default=OfferStatus.DRAFT)
    source_key = models.CharField(max_length=180, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["activity_id", "occurrence_id", "unit_price", "name", "id"]
        indexes = [
            models.Index(fields=["activity", "status"], name="commerce_offer_activity_idx"),
            models.Index(fields=["occurrence", "status"], name="commerce_offer_occurrence_idx"),
            models.Index(fields=["available_from", "available_until"], name="commerce_offer_window_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="commerce_offer_price_nonnegative"),
            models.CheckConstraint(condition=Q(max_quantity__isnull=True) | Q(max_quantity__gte=F("min_quantity")), name="commerce_offer_quantity_range"),
            models.CheckConstraint(condition=Q(available_until__isnull=True) | Q(available_from__isnull=True) | Q(available_until__gt=F("available_from")), name="commerce_offer_window_valid"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.currency = (self.currency or "USD").strip().upper()
        if len(self.currency) != 3 or not self.currency.isalpha():
            errors["currency"] = "La devise doit être un code ISO 4217 de trois lettres."
        if self.occurrence_id and self.activity_id and self.occurrence.activity_id != self.activity_id:
            errors["occurrence"] = "L’Occurrence doit appartenir à la même Activity que l’Offer."
        if self.capacity_pool_id and self.activity_id:
            if self.capacity_pool.activity_id != self.activity_id:
                errors["capacity_pool"] = "Le CapacityPool appartient à une autre Activity."
            if self.occurrence_id and self.capacity_pool.occurrence_id and self.capacity_pool.occurrence_id != self.occurrence_id:
                errors["capacity_pool"] = "Le CapacityPool cible une autre Occurrence."
        if self.payment_mode == PaymentMode.NONE and self.unit_price != Decimal("0.00"):
            errors["payment_mode"] = "payment_mode=none exige un prix nul."
        if self.available_from and self.available_until and self.available_until <= self.available_from:
            errors["available_until"] = "La fin de disponibilité doit être postérieure au début."
        if self.max_quantity is not None and self.max_quantity < self.min_quantity:
            errors["max_quantity"] = "Le maximum doit être supérieur ou égal au minimum."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "USD").strip().upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def allowed_payment_modes(self):
        if not self.pk:
            return [self.payment_mode]
        configured = list(self.payment_options.order_by("mode").values_list("mode", flat=True))
        return configured or [self.payment_mode]

    def allows_payment_mode(self, mode):
        return mode in self.allowed_payment_modes

    @property
    def is_free(self):
        return self.unit_price == Decimal("0.00")

    @property
    def is_currently_available(self):
        now = timezone.now()
        if self.status != OfferStatus.ACTIVE:
            return False
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now >= self.available_until:
            return False
        if self.capacity_pool_id:
            from capacity.selectors import is_sold_out
            if is_sold_out(self.capacity_pool, now=now):
                return False
        return True

    def __str__(self):
        return f"{self.activity} — {self.name}"


class OfferPaymentOption(models.Model):
    """Queryable set of payment modes a participant may choose for one Offer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name="payment_options")
    mode = models.CharField(max_length=24, choices=PaymentMode.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["offer_id", "mode"]
        constraints = [
            models.UniqueConstraint(fields=["offer", "mode"], name="commerce_offer_payment_mode_unique")
        ]
        indexes = [models.Index(fields=["mode", "offer"], name="commerce_offer_paymode_idx")]

    def clean(self):
        super().clean()
        if self.offer_id and self.mode == PaymentMode.NONE and self.offer.unit_price != Decimal("0.00"):
            raise ValidationError({"mode": "Le mode sans paiement exige une Offer gratuite."})
        if self.offer_id and self.offer.unit_price == Decimal("0.00") and self.mode != PaymentMode.NONE:
            raise ValidationError({"mode": "Une Offer gratuite n’accepte que le mode sans paiement."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.offer} — {self.get_mode_display()}"


class CommerceOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=24, unique=True, editable=False)
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.PROTECT,
        related_name="commerce_orders",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="commerce_orders",
        null=True,
        blank=True,
    )
    payee_space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="commerce_orders",
        null=True,
        blank=True,
    )
    payee_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payee_commerce_orders",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=CommerceOrderStatus.choices,
        default=CommerceOrderStatus.PENDING,
    )
    currency = models.CharField(max_length=3, default="USD")
    payment_mode = models.CharField(max_length=24, choices=PaymentMode.choices, default=PaymentMode.NONE)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    expires_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=128, unique=True, null=True, blank=True)
    source_key = models.CharField(max_length=180, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["buyer", "status"], name="commerce_order_buyer_idx"),
            models.Index(fields=["payee_space", "status"], name="commerce_order_payee_idx"),
            models.Index(fields=["payee_profile", "status"], name="commerce_order_ppayee_idx"),
            models.Index(fields=["journey"], name="commerce_order_journey_idx"),
            models.Index(fields=["created_at"], name="commerce_order_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="commerce_order_subtotal_nonnegative"),
            models.CheckConstraint(condition=Q(discount_total__gte=0), name="commerce_order_discount_nonnegative"),
            models.CheckConstraint(condition=Q(total__gte=0), name="commerce_order_total_nonnegative"),
            models.CheckConstraint(condition=Q(discount_total__lte=F("subtotal")), name="commerce_order_discount_lte_subtotal"),
            models.CheckConstraint(condition=Q(total=F("subtotal") - F("discount_total")), name="commerce_order_total_consistent"),
            models.CheckConstraint(
                condition=Q(payee_space__isnull=True) | Q(payee_profile__isnull=True),
                name="commerce_order_single_payee",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.currency = (self.currency or "USD").strip().upper()
        if len(self.currency) != 3 or not self.currency.isalpha():
            errors["currency"] = "La devise doit contenir exactement trois lettres."
        if self.discount_total < 0 or self.subtotal < 0 or self.total < 0:
            errors["total"] = "Les montants d’une commande ne peuvent pas être négatifs."
        if self.discount_total > self.subtotal:
            errors["discount_total"] = "La remise ne peut pas dépasser le sous-total."
        if self.total != self.subtotal - self.discount_total:
            errors["total"] = "Le total doit être égal au sous-total moins la remise."
        if self.payment_mode == PaymentMode.NONE and self.total != Decimal("0.00"):
            errors["payment_mode"] = "Une commande sans paiement attendu doit avoir un total nul."
        if self.payee_space_id and self.payee_profile_id:
            errors["payee_profile"] = "Une commande ne peut avoir qu’un seul bénéficiaire financier logique."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "USD").strip().upper()
        if not self.reference:
            self.reference = f"COM-{uuid.uuid4().hex[:12].upper()}"
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = CommerceOrder.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez les services Commerce pour changer l’état de la commande."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    @property
    def payee(self):
        return self.payee_space or self.payee_profile

    def __str__(self):
        return self.reference


class CommerceOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(CommerceOrder, on_delete=models.CASCADE, related_name="items")
    offer = models.ForeignKey(Offer, on_delete=models.PROTECT, related_name="order_items")
    beneficiary = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="commerce_order_items",
        null=True,
        blank=True,
    )
    external_beneficiary = models.ForeignKey(
        "journeys.ExternalBeneficiary",
        on_delete=models.PROTECT,
        related_name="commerce_order_items",
        null=True,
        blank=True,
    )
    capacity_reservation = models.ForeignKey(
        "capacity.CapacityReservation",
        on_delete=models.PROTECT,
        related_name="commerce_items",
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    label_snapshot = models.CharField(max_length=180)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["order"], name="commerce_item_order_idx"),
            models.Index(fields=["offer"], name="commerce_item_offer_idx"),
            models.Index(fields=["external_beneficiary"], name="commerce_item_extben_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="commerce_item_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="commerce_item_price_nonnegative"),
            models.CheckConstraint(condition=Q(line_subtotal__gte=0), name="commerce_item_subtotal_nonnegative"),
            models.CheckConstraint(condition=Q(discount_total__gte=0), name="commerce_item_discount_nonnegative"),
            models.CheckConstraint(condition=Q(line_total__gte=0), name="commerce_item_total_nonnegative"),
            models.CheckConstraint(condition=Q(discount_total__lte=F("line_subtotal")), name="commerce_item_discount_lte_subtotal"),
            models.CheckConstraint(condition=Q(line_total=F("line_subtotal") - F("discount_total")), name="commerce_item_total_consistent"),
            models.CheckConstraint(
                condition=Q(beneficiary__isnull=True) | Q(external_beneficiary__isnull=True),
                name="commerce_item_single_beneficiary",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.order_id and self.offer_id:
            if self.offer.activity_id != self.order.journey.activity_id:
                errors["offer"] = "L’Offer appartient à une autre Activity que la Démarche."
        if self.beneficiary_id and self.external_beneficiary_id:
            errors["beneficiary"] = "Une ligne Commerce ne peut cibler qu’un seul bénéficiaire."
        if self.capacity_reservation_id:
            if self.capacity_reservation.journey_id != self.order.journey_id:
                errors["capacity_reservation"] = "La réservation de capacité appartient à une autre Démarche."
            if self.offer.capacity_pool_id and self.capacity_reservation.pool_id != self.offer.capacity_pool_id:
                errors["capacity_reservation"] = "La réservation ne correspond pas au pool de l’Offer."
        expected_subtotal = self.unit_price * self.quantity
        if self.line_subtotal != expected_subtotal:
            errors["line_subtotal"] = "Le sous-total de ligne est incohérent avec le prix snapshot et la quantité."
        if self.discount_total < 0 or self.discount_total > self.line_subtotal:
            errors["discount_total"] = "La remise de ligne est invalide."
        if self.line_total != self.line_subtotal - self.discount_total:
            errors["line_total"] = "Le total de ligne est incohérent."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order.reference} — {self.label_snapshot} × {self.quantity}"
