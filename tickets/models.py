import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.signing import Signer
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from events.models import Event, EventStatus


QR_SIGNING_SALT = "makolo.tickets.qr"


class TicketOrderStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    CONFIRMED = "confirmed", "Confirmée"
    CANCELLED = "cancelled", "Annulée"
    EXPIRED = "expired", "Expirée"


class TicketStatus(models.TextChoices):
    VALID = "valid", "Valide"
    USED = "used", "Utilisé"
    CANCELLED = "cancelled", "Annulé"
    REFUNDED = "refunded", "Remboursé"


class WaitlistStatus(models.TextChoices):
    WAITING = "waiting", "En attente"
    OFFERED = "offered", "Place proposée"
    CONVERTED = "converted", "Billet obtenu"
    CANCELLED = "cancelled", "Retiré"
    EXPIRED = "expired", "Offre expirée"


class TransferStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ACCEPTED = "accepted", "Accepté"
    DECLINED = "declined", "Refusé"
    CANCELLED = "cancelled", "Annulé"
    EXPIRED = "expired", "Expiré"


class TicketType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="ticket_types",
    )
    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=3, default="USD")
    quantity_total = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Laisser vide pour un stock illimité.",
    )
    reserved_quantity = models.PositiveIntegerField(default=0, editable=False)
    issued_quantity = models.PositiveIntegerField(default=0, editable=False)
    sales_start_at = models.DateTimeField(null=True, blank=True)
    sales_end_at = models.DateTimeField(null=True, blank=True)
    min_per_order = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    max_per_order = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price", "name"]
        verbose_name = "type de billet"
        verbose_name_plural = "types de billets"
        constraints = [
            models.UniqueConstraint(
                fields=["event", "slug"],
                name="ticket_type_event_slug_unique",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.currency = (self.currency or "USD").upper()

        if len(self.currency) != 3:
            errors["currency"] = "La devise doit contenir exactement 3 lettres."

        if self.sales_start_at and self.sales_end_at:
            if self.sales_end_at <= self.sales_start_at:
                errors["sales_end_at"] = (
                    "La fin de vente doit être postérieure au début de vente."
                )

        if self.max_per_order < self.min_per_order:
            errors["max_per_order"] = (
                "Le maximum par commande doit être supérieur ou égal au minimum."
            )

        if self.quantity_total is not None:
            committed = self.reserved_quantity + self.issued_quantity
            if committed > self.quantity_total:
                errors["quantity_total"] = (
                    "Le stock total ne peut pas être inférieur au stock déjà réservé ou émis."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "USD").upper()
        if not self.slug:
            base = slugify(self.name)[:130] or "billet"
            candidate = base
            suffix = 2
            while TicketType.objects.exclude(pk=self.pk).filter(
                event=self.event,
                slug=candidate,
            ).exists():
                candidate = f"{base[:145]}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def is_free(self):
        return self.price == 0

    @property
    def available_quantity(self):
        if self.quantity_total is None:
            return None
        return max(
            self.quantity_total - self.reserved_quantity - self.issued_quantity,
            0,
        )

    @property
    def is_on_sale(self):
        now = timezone.now()
        if not self.is_active or self.event.status != EventStatus.PUBLISHED:
            return False
        if not self.event.is_registration_open:
            return False
        if self.sales_start_at and now < self.sales_start_at:
            return False
        if self.sales_end_at and now > self.sales_end_at:
            return False
        if self.available_quantity == 0:
            return False
        return True

    def __str__(self):
        return f"{self.event.title} — {self.name}"


class TicketOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=24, unique=True, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="ticket_orders",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ticket_orders",
        null=True,
        blank=True,
    )
    customer_name = models.CharField(max_length=180)
    customer_email = models.EmailField()
    status = models.CharField(
        max_length=20,
        choices=TicketOrderStatus.choices,
        default=TicketOrderStatus.PENDING,
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    expires_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "commande de billets"
        verbose_name_plural = "commandes de billets"
        indexes = [
            models.Index(fields=["event", "status"]),
            models.Index(fields=["buyer", "status"]),
        ]

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "USD").upper()
        if not self.reference:
            self.reference = f"MKO-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return bool(
            self.status == TicketOrderStatus.PENDING
            and self.expires_at
            and timezone.now() >= self.expires_at
        )

    def __str__(self):
        return self.reference


class TicketOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        TicketOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    ticket_type = models.ForeignKey(
        TicketType,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "ticket_type"],
                name="ticket_order_item_type_unique",
            )
        ]

    def clean(self):
        super().clean()
        if self.ticket_type_id and self.order_id:
            if self.ticket_type.event_id != self.order.event_id:
                raise ValidationError(
                    {"ticket_type": "Le type de billet appartient à un autre événement."}
                )

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.order.reference} — {self.ticket_type.name} × {self.quantity}"


class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    ticket_type = models.ForeignKey(
        TicketType,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    order = models.ForeignKey(
        TicketOrder,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="tickets",
        null=True,
        blank=True,
    )
    holder_name = models.CharField(max_length=180)
    holder_email = models.EmailField()
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.VALID,
    )
    issued_at = models.DateTimeField(default=timezone.now)
    used_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["event", "status"]),
            models.Index(fields=["owner", "status"]),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.ticket_type_id and self.event_id:
            if self.ticket_type.event_id != self.event_id:
                errors["ticket_type"] = "Le type de billet appartient à un autre événement."
        if self.order_id and self.event_id:
            if self.order.event_id != self.event_id:
                errors["order"] = "La commande appartient à un autre événement."
        if errors:
            raise ValidationError(errors)

    @property
    def qr_token(self):
        return Signer(salt=QR_SIGNING_SALT).sign(str(self.code))

    @property
    def is_valid(self):
        return (
            self.status == TicketStatus.VALID
            and self.event.status == EventStatus.PUBLISHED
            and timezone.now() < self.event.end_at
        )

    def __str__(self):
        return f"{self.code} — {self.event.title}"


class TicketWaitlistEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_type = models.ForeignKey(
        TicketType,
        on_delete=models.CASCADE,
        related_name="waitlist_entries",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_waitlist_entries",
    )
    requested_quantity = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    status = models.CharField(
        max_length=16,
        choices=WaitlistStatus.choices,
        default=WaitlistStatus.WAITING,
    )
    offered_order = models.OneToOneField(
        TicketOrder,
        on_delete=models.SET_NULL,
        related_name="waitlist_entry",
        null=True,
        blank=True,
    )
    offered_at = models.DateTimeField(null=True, blank=True)
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["ticket_type", "user"],
                condition=models.Q(status__in=[WaitlistStatus.WAITING, WaitlistStatus.OFFERED]),
                name="ticket_waitlist_one_active_user",
            ),
        ]
        indexes = [
            models.Index(
                fields=["ticket_type", "status", "created_at"],
                name="ticket_waitlist_queue_idx",
            ),
            models.Index(
                fields=["user", "status", "created_at"],
                name="ticket_waitlist_user_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.ticket_type_id and self.requested_quantity > self.ticket_type.max_per_order:
            raise ValidationError(
                {"requested_quantity": "La quantité demandée dépasse le maximum par commande."}
            )

    @property
    def is_offer_active(self):
        return bool(
            self.status == WaitlistStatus.OFFERED
            and self.offered_order_id
            and self.offer_expires_at
            and timezone.now() < self.offer_expires_at
        )

    def __str__(self):
        return f"{self.user} — {self.ticket_type} — {self.get_status_display()}"


class TicketTransfer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="transfers",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="outgoing_ticket_transfers",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="incoming_ticket_transfers",
    )
    recipient_email = models.EmailField()
    status = models.CharField(
        max_length=16,
        choices=TransferStatus.choices,
        default=TransferStatus.PENDING,
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["ticket"],
                condition=models.Q(status=TransferStatus.PENDING),
                name="ticket_transfer_one_pending",
            ),
        ]
        indexes = [
            models.Index(
                fields=["recipient", "status", "created_at"],
                name="ticket_transfer_recipient_idx",
            ),
            models.Index(
                fields=["sender", "status", "created_at"],
                name="ticket_transfer_sender_idx",
            ),
            models.Index(
                fields=["status", "expires_at"],
                name="ticket_transfer_expiry_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.sender_id and self.recipient_id and self.sender_id == self.recipient_id:
            raise ValidationError({"recipient": "Vous ne pouvez pas transférer un billet à vous-même."})

    @property
    def is_pending_active(self):
        return self.status == TransferStatus.PENDING and timezone.now() < self.expires_at

    def __str__(self):
        return f"{self.ticket} — {self.sender} → {self.recipient}"
