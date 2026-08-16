import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.signing import Signer
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify

from access.models import AccessStatus
from commerce.models import CommerceOrderStatus, OfferStatus, PaymentMode
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


class TicketQuerySet(models.QuerySet):
    def update(self, **kwargs):
        sync_required = bool({"status", "owner", "owner_id", "code"} & set(kwargs))
        ticket_ids = list(self.values_list("pk", flat=True)) if sync_required else []
        updated = super().update(**kwargs)
        if ticket_ids:
            from .journey_access_bridge import sync_ticket_access_ids

            sync_ticket_access_ids(ticket_ids)
        return updated


class TicketManager(models.Manager.from_queryset(TicketQuerySet)):
    def bulk_create(self, objs, **kwargs):
        created = super().bulk_create(objs, **kwargs)
        if created:
            from .journey_access_bridge import sync_ticket_access_ids

            sync_ticket_access_ids([ticket.pk for ticket in created])
        return created


class TicketTypeManager(models.Manager):
    """Compatibility constructor that persists commercial values canonically."""

    @transaction.atomic
    def create(self, **kwargs):
        if kwargs.get("offer") is not None and kwargs.get("capacity_pool") is not None:
            return super().create(**kwargs)

        from capacity.models import CapacityPool
        from commerce.models import Offer

        event = kwargs.get("event")
        if event is None and kwargs.get("event_id"):
            event = Event.objects.select_related("activity").get(pk=kwargs["event_id"])
        if event is None:
            raise TypeError("TicketType exige un Event.")
        occurrence = event.primary_occurrence
        if occurrence is None:
            raise ValidationError("Le type de billet exige une Occurrence principale.")

        price = kwargs.pop("price", 0)
        currency = (kwargs.pop("currency", "USD") or "USD").upper()
        quantity_total = kwargs.pop("quantity_total", None)
        kwargs.pop("reserved_quantity", 0)
        kwargs.pop("issued_quantity", 0)
        sales_start_at = kwargs.pop("sales_start_at", None)
        sales_end_at = kwargs.pop("sales_end_at", None)
        min_per_order = kwargs.pop("min_per_order", 1)
        max_per_order = kwargs.pop("max_per_order", 10)
        is_active = kwargs.pop("is_active", True)
        ticket_type_id = kwargs.setdefault("id", uuid.uuid4())
        name = kwargs.get("name") or "Billet"
        description = kwargs.get("description", "")

        pool = CapacityPool.objects.create(
            activity=event.activity,
            occurrence=occurrence,
            label=name,
            total_quantity=quantity_total,
            is_active=is_active,
            source_key=f"ticket-type:{ticket_type_id}",
        )
        offer = Offer.objects.create(
            activity=event.activity,
            occurrence=occurrence,
            capacity_pool=pool,
            name=name,
            description=description,
            unit_price=price,
            currency=currency,
            payment_mode=PaymentMode.NONE if price == 0 else PaymentMode.UPFRONT,
            available_from=sales_start_at,
            available_until=sales_end_at,
            min_quantity=min_per_order,
            max_quantity=max_per_order,
            status=OfferStatus.ACTIVE if is_active else OfferStatus.INACTIVE,
            source_key=f"ticket-type:{ticket_type_id}",
        )
        kwargs["offer"] = offer
        kwargs["capacity_pool"] = pool
        return super().create(**kwargs)


class TicketType(models.Model):
    """Event vocabulary for one canonical Offer and CapacityPool."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ticket_types")
    offer = models.OneToOneField(
        "commerce.Offer",
        on_delete=models.PROTECT,
        related_name="ticket_type",
    )
    capacity_pool = models.OneToOneField(
        "capacity.CapacityPool",
        on_delete=models.PROTECT,
        related_name="ticket_type",
    )
    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(
        default=True,
        help_text="Visible et achetable depuis les parcours participants publics.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TicketTypeManager()

    class Meta:
        ordering = ["name", "id"]
        verbose_name = "type de billet"
        verbose_name_plural = "types de billets"
        constraints = [
            models.UniqueConstraint(fields=["event", "slug"], name="ticket_type_event_slug_unique"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.offer_id and self.capacity_pool_id:
            if self.offer.capacity_pool_id != self.capacity_pool_id:
                errors["offer"] = "L’Offer doit utiliser le CapacityPool de ce type de billet."
            if self.event_id and self.offer.activity_id != self.event.activity_id:
                errors["offer"] = "L’Offer doit appartenir à l’Activity de l’événement."
            if self.event_id and self.capacity_pool.activity_id != self.event.activity_id:
                errors["capacity_pool"] = "Le CapacityPool doit appartenir à l’Activity de l’événement."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:130] or "billet"
            candidate = base
            suffix = 2
            while TicketType.objects.exclude(pk=self.pk).filter(event=self.event, slug=candidate).exists():
                candidate = f"{base[:145]}-{suffix}"
                suffix += 1
            self.slug = candidate
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def price(self):
        return self.offer.unit_price

    @property
    def currency(self):
        return self.offer.currency

    @property
    def quantity_total(self):
        return self.capacity_pool.total_quantity

    @property
    def reserved_quantity(self):
        from capacity.selectors import capacity_availability
        return capacity_availability(self.capacity_pool).held

    @property
    def issued_quantity(self):
        from capacity.selectors import capacity_availability
        return capacity_availability(self.capacity_pool).committed

    @property
    def sales_start_at(self):
        return self.offer.available_from

    @property
    def sales_end_at(self):
        return self.offer.available_until

    @property
    def min_per_order(self):
        return self.offer.min_quantity

    @property
    def max_per_order(self):
        return self.offer.max_quantity or 10**9

    @property
    def is_active(self):
        return self.offer.status == OfferStatus.ACTIVE and self.capacity_pool.is_active

    @property
    def is_free(self):
        return self.offer.is_free

    @property
    def available_quantity(self):
        from capacity.selectors import available_quantity
        return available_quantity(self.capacity_pool)

    @property
    def is_on_sale(self):
        return bool(
            self.is_public
            and self.event.status == EventStatus.PUBLISHED
            and self.event.is_registration_open
            and self.offer.is_currently_available
        )

    def __str__(self):
        return f"{self.event.title} — {self.name}"


class TicketOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=24, unique=True, editable=False)
    idempotency_key = models.UUIDField(unique=True, null=True, blank=True, editable=False)
    idempotency_fingerprint = models.CharField(max_length=64, blank=True, editable=False)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="ticket_orders")
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ticket_orders",
        null=True,
        blank=True,
    )
    journey = models.OneToOneField(
        "journeys.Journey",
        on_delete=models.SET_NULL,
        related_name="ticket_order",
        null=True,
        blank=True,
    )
    commerce_order = models.OneToOneField(
        "commerce.CommerceOrder",
        on_delete=models.SET_NULL,
        related_name="ticket_order",
        null=True,
        blank=True,
    )
    customer_name = models.CharField(max_length=180)
    customer_email = models.EmailField()
    # Compatibility projection for historical endpoints/provider callbacks.
    status = models.CharField(max_length=20, choices=TicketOrderStatus.choices, default=TicketOrderStatus.PENDING)
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
    def canonical_status(self):
        return self.commerce_order.status if self.commerce_order_id else self.status

    @property
    def canonical_total(self):
        return self.commerce_order.total if self.commerce_order_id else self.total_amount

    @property
    def canonical_currency(self):
        return self.commerce_order.currency if self.commerce_order_id else self.currency

    @property
    def is_expired(self):
        if self.commerce_order_id:
            return self.commerce_order.status == CommerceOrderStatus.EXPIRED or bool(
                self.commerce_order.status == CommerceOrderStatus.PENDING
                and self.commerce_order.expires_at
                and timezone.now() >= self.commerce_order.expires_at
            )
        return bool(
            self.status == TicketOrderStatus.PENDING
            and self.expires_at
            and timezone.now() >= self.expires_at
        )

    def __str__(self):
        return self.reference


class TicketOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(TicketOrder, on_delete=models.CASCADE, related_name="items")
    ticket_type = models.ForeignKey(TicketType, on_delete=models.PROTECT, related_name="order_items")
    commerce_item = models.OneToOneField(
        "commerce.CommerceOrderItem",
        on_delete=models.SET_NULL,
        related_name="ticket_order_item",
        null=True,
        blank=True,
    )
    # Snapshot compatibility; CommerceOrderItem is canonical for new decisions.
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["order", "ticket_type"], name="ticket_order_item_type_unique")
        ]

    def clean(self):
        super().clean()
        if self.ticket_type_id and self.order_id and self.ticket_type.event_id != self.order.event_id:
            raise ValidationError({"ticket_type": "Le type de billet appartient à un autre événement."})

    @property
    def line_total(self):
        if self.commerce_item_id:
            return self.commerce_item.line_total
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.order.reference} — {self.ticket_type.name} × {self.quantity}"


class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Legacy code remains solely for historical tickets that predate AccessCredential.
    code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="tickets")
    ticket_type = models.ForeignKey(TicketType, on_delete=models.PROTECT, related_name="tickets")
    order = models.ForeignKey(TicketOrder, on_delete=models.PROTECT, related_name="tickets")
    access = models.OneToOneField(
        "access.Access",
        on_delete=models.SET_NULL,
        related_name="ticket",
        null=True,
        blank=True,
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
    # Compatibility projection for legacy tickets. New tickets are governed by Access.
    status = models.CharField(max_length=20, choices=TicketStatus.choices, default=TicketStatus.VALID)
    issued_at = models.DateTimeField(default=timezone.now)
    used_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TicketManager()

    class Meta:
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["event", "status"]),
            models.Index(fields=["owner", "status"]),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.ticket_type_id and self.event_id and self.ticket_type.event_id != self.event_id:
            errors["ticket_type"] = "Le type de billet appartient à un autre événement."
        if self.order_id and self.event_id and self.order.event_id != self.event_id:
            errors["order"] = "La commande appartient à un autre événement."
        if errors:
            raise ValidationError(errors)

    @property
    def qr_token(self):
        if self.access_id:
            from access.models import CredentialStatus
            from access.services import render_access_credential

            credential = self.access.credentials.filter(status=CredentialStatus.ACTIVE).order_by("-version").first()
            if credential:
                return render_access_credential(credential)
        # Only legacy tickets without Access may emit the historical signed code.
        return Signer(salt=QR_SIGNING_SALT).sign(str(self.code))

    @property
    def display_status(self):
        if not self.access_id:
            return self.status
        mapping = {
            AccessStatus.VALID: TicketStatus.VALID,
            AccessStatus.USED: TicketStatus.USED,
            AccessStatus.CANCELLED: TicketStatus.CANCELLED,
            AccessStatus.REVOKED: TicketStatus.REFUNDED,
            AccessStatus.EXPIRED: TicketStatus.CANCELLED,
            AccessStatus.TRANSFERRED: TicketStatus.CANCELLED,
            AccessStatus.PENDING: TicketStatus.CANCELLED,
        }
        return mapping[self.access.status]

    @property
    def is_valid(self):
        if self.access_id:
            now = timezone.now()
            return bool(
                self.access.status == AccessStatus.VALID
                and (self.access.valid_from is None or now >= self.access.valid_from)
                and (self.access.valid_until is None or now < self.access.valid_until)
                and self.event.status == EventStatus.PUBLISHED
            )
        return bool(
            self.status == TicketStatus.VALID
            and self.event.status == EventStatus.PUBLISHED
            and self.event.end_at
            and timezone.now() < self.event.end_at
        )

    def __str__(self):
        return f"{self.code} — {self.event.title}"


class TicketWaitlistEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE, related_name="waitlist_entries")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_waitlist_entries",
    )
    requested_quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=16, choices=WaitlistStatus.choices, default=WaitlistStatus.WAITING)
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
            models.Index(fields=["ticket_type", "status", "created_at"], name="ticket_waitlist_queue_idx"),
            models.Index(fields=["user", "status", "created_at"], name="ticket_waitlist_user_idx"),
        ]

    def clean(self):
        super().clean()
        if self.ticket_type_id and self.requested_quantity > self.ticket_type.max_per_order:
            raise ValidationError({"requested_quantity": "La quantité demandée dépasse le maximum par commande."})

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
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="transfers")
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
    status = models.CharField(max_length=16, choices=TransferStatus.choices, default=TransferStatus.PENDING)
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
            models.Index(fields=["recipient", "status", "created_at"], name="ticket_transfer_recipient_idx"),
            models.Index(fields=["sender", "status", "created_at"], name="ticket_transfer_sender_idx"),
            models.Index(fields=["status", "expires_at"], name="ticket_transfer_expiry_idx"),
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
