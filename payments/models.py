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


class PaymentObligationReason(models.TextChoices):
    COMMERCE = "commerce", "Commerce"
    OPPORTUNITY_REQUIREMENT = "opportunity_requirement", "Requirement Opportunity"
    SERVICE_PROCESS = "service_process", "Processus Service"
    ACCESS_REQUIREMENT = "access_requirement", "Condition d’accès"
    OTHER = "other", "Autre"


class PaymentObligationProcessingMode(models.TextChoices):
    MAKOLO_PROVIDER = "makolo_provider", "Provider Makolo"
    EXTERNAL = "external", "Paiement externe"


class PaymentObligationStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    PROCESSING = "processing", "En traitement"
    SATISFIED = "satisfied", "Satisfaite"
    WAIVED = "waived", "Dispensée"
    EXPIRED = "expired", "Expirée"
    CANCELLED = "cancelled", "Annulée"
    REFUNDED = "refunded", "Remboursée"


class PaymentEvidenceStatus(models.TextChoices):
    SUBMITTED = "submitted", "Soumise"
    VERIFIED = "verified", "Vérifiée"
    REJECTED = "rejected", "Rejetée"


class RefundStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    SUCCEEDED = "succeeded", "Réussi"
    FAILED = "failed", "Échoué"
    CANCELLED = "cancelled", "Annulé"


class PaymentObligation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.PROTECT,
        related_name="payment_obligations",
    )
    commerce_order = models.ForeignKey(
        "commerce.CommerceOrder",
        on_delete=models.PROTECT,
        related_name="payment_obligations",
        null=True,
        blank=True,
    )
    step = models.ForeignKey(
        "journeys.JourneyStep",
        on_delete=models.PROTECT,
        related_name="payment_obligations",
        null=True,
        blank=True,
    )
    reason = models.CharField(max_length=32, choices=PaymentObligationReason.choices)
    label = models.CharField(max_length=220)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, default="USD")
    processing_mode = models.CharField(max_length=24, choices=PaymentObligationProcessingMode.choices)
    status = models.CharField(max_length=16, choices=PaymentObligationStatus.choices, default=PaymentObligationStatus.PENDING)
    payee_space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payment_obligations",
        null=True,
        blank=True,
    )
    payee_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payee_payment_obligations",
        null=True,
        blank=True,
    )
    external_payee_name = models.CharField(max_length=220, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    satisfied_at = models.DateTimeField(null=True, blank=True)
    source_key = models.CharField(max_length=180, unique=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_payment_obligations",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["journey", "status"], name="payobl_journey_status_idx"),
            models.Index(fields=["step", "status"], name="payobl_step_status_idx"),
            models.Index(fields=["commerce_order"], name="payobl_commerce_idx"),
            models.Index(fields=["processing_mode", "status"], name="payobl_mode_status_idx"),
            models.Index(fields=["due_at", "status"], name="payobl_due_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payobl_amount_positive"),
            models.CheckConstraint(
                condition=(
                    Q(payee_space__isnull=False, payee_profile__isnull=True, external_payee_name="")
                    | Q(payee_space__isnull=True, payee_profile__isnull=False, external_payee_name="")
                    | (Q(payee_space__isnull=True, payee_profile__isnull=True) & ~Q(external_payee_name=""))
                ),
                name="payobl_exactly_one_payee",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.currency = (self.currency or "USD").strip().upper()
        self.label = (self.label or "").strip()
        self.external_payee_name = (self.external_payee_name or "").strip()
        if len(self.currency) != 3 or not self.currency.isalpha():
            errors["currency"] = "La devise doit être un code ISO 4217 de trois lettres."
        if self.amount is None or self.amount <= 0:
            errors["amount"] = "Le montant d’une obligation doit être strictement positif."
        payees = int(bool(self.payee_space_id)) + int(bool(self.payee_profile_id)) + int(bool(self.external_payee_name))
        if payees != 1:
            errors["external_payee_name"] = "Une obligation doit avoir exactement un bénéficiaire économique."
        if self.commerce_order_id:
            if self.commerce_order.journey_id != self.journey_id:
                errors["commerce_order"] = "La CommerceOrder doit appartenir à la même Journey."
            if self.reason == PaymentObligationReason.COMMERCE:
                if self.amount != self.commerce_order.total:
                    errors["amount"] = "L’obligation Commerce doit correspondre au total de la CommerceOrder."
                if self.currency != self.commerce_order.currency:
                    errors["currency"] = "L’obligation Commerce doit utiliser la devise de la CommerceOrder."
        if self.reason == PaymentObligationReason.COMMERCE and not self.commerce_order_id:
            errors["commerce_order"] = "Une obligation Commerce doit référencer sa CommerceOrder canonique."
        if self.step_id and self.step.journey_id != self.journey_id:
            errors["step"] = "La JourneyStep doit appartenir à la même Journey."
        if self.status == PaymentObligationStatus.SATISFIED and self.satisfied_at is None:
            errors["satisfied_at"] = "Une obligation satisfaite doit conserver sa date de satisfaction."
        if self.status != PaymentObligationStatus.SATISFIED and self.satisfied_at is not None:
            errors["satisfied_at"] = "Seule une obligation satisfaite porte satisfied_at."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "USD").strip().upper()
        self.label = (self.label or "").strip()
        self.external_payee_name = (self.external_payee_name or "").strip()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = PaymentObligation.objects.filter(pk=self.pk).values("status", "satisfied_at").first()
            if previous and (previous["status"] != self.status or previous["satisfied_at"] != self.satisfied_at):
                raise ValidationError({"status": "Utilisez les services Payments pour changer l’état d’une obligation."})
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def delete(self, *args, **kwargs):
        if self.pk and PaymentObligation.objects.filter(pk=self.pk).exists():
            raise ValidationError("Une PaymentObligation auditée ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.label} — {self.amount} {self.currency}"


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=24, unique=True, editable=False)
    order = models.ForeignKey(
        TicketOrder,
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
    )
    commerce_order = models.ForeignKey(
        "commerce.CommerceOrder",
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
    )
    obligation = models.ForeignKey(
        PaymentObligation,
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
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
            models.Index(fields=["commerce_order", "status"], name="pay_commerce_status_idx"),
            models.Index(fields=["obligation", "status"], name="pay_obligation_status_idx"),
            models.Index(fields=["provider", "status"], name="pay_provider_status_idx"),
            models.Index(fields=["created_at"], name="pay_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(order__isnull=False) | Q(commerce_order__isnull=False) | Q(obligation__isnull=False),
                name="payment_has_order_source",
            ),
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(status=PaymentStatus.SUCCEEDED),
                name="payment_one_success_order",
            ),
            models.UniqueConstraint(
                fields=["commerce_order"],
                condition=Q(status=PaymentStatus.SUCCEEDED) & Q(commerce_order__isnull=False),
                name="payment_one_success_commerce_order",
            ),
            models.UniqueConstraint(
                fields=["obligation"],
                condition=Q(status=PaymentStatus.SUCCEEDED) & Q(obligation__isnull=False),
                name="payment_one_success_obligation",
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
        if len(self.currency) != 3 or not self.currency.isalpha():
            errors["currency"] = "La devise doit contenir exactement 3 lettres."
        if not self.order_id and not self.commerce_order_id and not self.obligation_id:
            errors["commerce_order"] = "Un paiement doit référencer une obligation ou une commande legacy."
        if self.order_id:
            if self.order.total_amount <= 0:
                errors["order"] = "Une commande gratuite ne nécessite pas de paiement."
            if self.amount != self.order.total_amount:
                errors["amount"] = "Le montant doit correspondre au total de la commande."
            if self.currency != self.order.currency:
                errors["currency"] = "La devise doit correspondre à celle de la commande."
        if self.commerce_order_id:
            if self.commerce_order.total <= 0:
                errors["commerce_order"] = "Une CommerceOrder gratuite ne nécessite pas de paiement."
            if self.amount != self.commerce_order.total:
                errors["amount"] = "Le montant doit correspondre au total commercial snapshot."
            if self.currency != self.commerce_order.currency:
                errors["currency"] = "La devise doit correspondre à celle de la CommerceOrder."
            if self.order_id and self.order.commerce_order_id not in {None, self.commerce_order_id}:
                errors["commerce_order"] = "Le Payment et le TicketOrder pointent vers des commandes canoniques différentes."
        if self.obligation_id:
            if self.obligation.processing_mode != PaymentObligationProcessingMode.MAKOLO_PROVIDER:
                errors["obligation"] = "Une obligation external est satisfaite par PaymentEvidence, pas par Payment."
            if self.amount != self.obligation.amount:
                errors["amount"] = "Le Payment doit régler l’intégralité de l’obligation."
            if self.currency != self.obligation.currency:
                errors["currency"] = "Le Payment doit utiliser la devise de l’obligation."
            if self.commerce_order_id and self.obligation.commerce_order_id not in {None, self.commerce_order_id}:
                errors["obligation"] = "Le Payment et l’obligation pointent vers des CommerceOrders différentes."
            if self.order_id and self.order.journey_id and self.order.journey_id != self.obligation.journey_id:
                errors["obligation"] = "Le Payment Event et l’obligation appartiennent à des Journeys différentes."
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
        if self.order_id:
            source = self.order.reference
        elif self.commerce_order_id:
            source = self.commerce_order.reference
        else:
            source = f"obligation:{self.obligation_id}"
        return f"{self.reference} — {source}"


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


class PaymentEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obligation = models.ForeignKey(PaymentObligation, on_delete=models.PROTECT, related_name="evidence")
    artifact = models.ForeignKey("journeys.JourneyArtifact", on_delete=models.PROTECT, related_name="payment_evidence")
    external_reference = models.CharField(max_length=240, blank=True)
    paid_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=PaymentEvidenceStatus.choices, default=PaymentEvidenceStatus.SUBMITTED)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="submitted_payment_evidence",
        null=True,
        blank=True,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="verified_payment_evidence",
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["obligation", "artifact"], name="payment_evidence_artifact_unique")]
        indexes = [models.Index(fields=["obligation", "status"], name="payevid_obligation_status_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.obligation_id:
            if self.obligation.processing_mode != PaymentObligationProcessingMode.EXTERNAL:
                errors["obligation"] = "PaymentEvidence est réservée aux obligations payées hors Makolo."
            if self.artifact_id and self.artifact.journey_id != self.obligation.journey_id:
                errors["artifact"] = "La preuve doit être un JourneyArtifact de la même Journey."
        if self.status == PaymentEvidenceStatus.SUBMITTED:
            if self.verified_at is not None or self.verified_by_id is not None:
                errors["verified_at"] = "Une preuve soumise n’est pas encore vérifiée."
        else:
            if self.verified_at is None:
                errors["verified_at"] = "Une preuve vérifiée ou rejetée doit conserver sa date de décision."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = PaymentEvidence.objects.filter(pk=self.pk).values("status", "verified_by_id", "verified_at", "review_note").first()
            current = {"status": self.status, "verified_by_id": self.verified_by_id, "verified_at": self.verified_at, "review_note": self.review_note}
            if previous and previous != current:
                raise ValidationError("Utilisez les services Payments pour décider une PaymentEvidence.")
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def delete(self, *args, **kwargs):
        raise ValidationError("Une PaymentEvidence auditée ne peut pas être supprimée.")

    def __str__(self):
        return f"{self.obligation_id} — {self.status}"


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
