import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from tickets.models import TicketOrder


class PaymentProvider(models.TextChoices):
    SANDBOX = "sandbox", "Sandbox Makolo"
    MANUAL = "manual", "Manuel"


class PaymentMethod(models.TextChoices):
    CARD = "card", "Carte"
    MOBILE_MONEY = "mobile_money", "Mobile Money"
    BANK_TRANSFER = "bank_transfer", "Virement bancaire"
    CASH = "cash", "Espèces"
    OTHER = "other", "Autre"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    PROCESSING = "processing", "En traitement"
    SUCCEEDED = "succeeded", "Réussi"
    FAILED = "failed", "Échoué"
    CANCELLED = "cancelled", "Annulé"
    REFUNDED = "refunded", "Remboursé"


class RefundStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    SUCCEEDED = "succeeded", "Réussi"
    FAILED = "failed", "Échoué"
    CANCELLED = "cancelled", "Annulé"


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=24, unique=True, editable=False)
    order = models.ForeignKey(
        TicketOrder,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_payments",
    )
    provider = models.CharField(
        max_length=32,
        choices=PaymentProvider.choices,
        default=PaymentProvider.SANDBOX,
    )
    method = models.CharField(
        max_length=32,
        choices=PaymentMethod.choices,
        default=PaymentMethod.OTHER,
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, default="USD")
    payer_name = models.CharField(max_length=180, blank=True)
    payer_email = models.EmailField(blank=True)
    payer_phone = models.CharField(max_length=40, blank=True)
    provider_reference = models.CharField(max_length=160, blank=True)
    idempotency_key = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
    )
    checkout_url = models.URLField(max_length=1000, blank=True)
    failure_code = models.CharField(max_length=120, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    succeeded_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "status"], name="pay_order_status_idx"),
            models.Index(fields=["provider", "status"], name="pay_provider_status_idx"),
            models.Index(fields=["created_at"], name="pay_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_amount_positive",
            ),
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(status=PaymentStatus.SUCCEEDED),
                name="payment_one_success_order",
            ),
            models.UniqueConstraint(
                fields=["provider", "provider_reference"],
                condition=~Q(provider_reference=""),
                name="payment_provider_ref_unique",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.currency = (self.currency or "USD").upper()
        if len(self.currency) != 3:
            errors["currency"] = "La devise doit contenir exactement 3 lettres."
        if self.order_id:
            if self.order.total_amount <= 0:
                errors["order"] = "Une commande gratuite ne nécessite pas de paiement."
            if self.amount != self.order.total_amount:
                errors["amount"] = "Le montant doit correspondre au total de la commande."
            if self.currency != self.order.currency:
                errors["currency"] = "La devise doit correspondre à celle de la commande."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "USD").upper()
        if not self.reference:
            self.reference = f"PAY-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    @property
    def is_terminal(self):
        return self.status in {
            PaymentStatus.SUCCEEDED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
            PaymentStatus.REFUNDED,
        }

    @property
    def refunded_amount(self):
        return sum(
            (refund.amount for refund in self.refunds.filter(status=RefundStatus.SUCCEEDED)),
            Decimal("0.00"),
        )

    @property
    def refundable_amount(self):
        if self.status not in {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED}:
            return Decimal("0.00")
        return max(self.amount - self.refunded_amount, Decimal("0.00"))

    def __str__(self):
        return f"{self.reference} — {self.order.reference}"


class Refund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=24, unique=True, editable=False)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="refunds",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_refunds",
    )
    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, default="USD")
    reason = models.CharField(max_length=500, blank=True)
    provider_reference = models.CharField(max_length=160, blank=True)
    idempotency_key = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
    )
    failure_message = models.CharField(max_length=500, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["payment", "status"], name="refund_payment_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="refund_amount_positive",
            ),
            models.UniqueConstraint(
                fields=["payment"],
                condition=Q(status=RefundStatus.SUCCEEDED),
                name="refund_one_success_payment",
            ),
        ]

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "USD").upper()
        if not self.reference:
            self.reference = f"RFD-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.reference


class PaymentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    provider = models.CharField(max_length=32, choices=PaymentProvider.choices)
    event_id = models.CharField(max_length=160, blank=True)
    event_type = models.CharField(max_length=120)
    signature_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    payload_hash = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    processing_error = models.CharField(max_length=500, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["provider", "event_type"], name="paye_provider_type_idx"),
            models.Index(fields=["processed", "received_at"], name="paye_processed_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"],
                condition=~Q(event_id=""),
                name="payment_event_provider_unique",
            ),
        ]

    def __str__(self):
        return f"{self.provider}:{self.event_type}:{self.event_id or self.id}"
