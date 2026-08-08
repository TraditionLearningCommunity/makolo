import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationCategory(models.TextChoices):
    EVENT = "event", "Événement"
    TICKET = "ticket", "Billetterie"
    PAYMENT = "payment", "Paiement"
    SECURITY = "security", "Sécurité"
    SYSTEM = "system", "Système"
    MARKETING = "marketing", "Marketing"


class NotificationKind(models.TextChoices):
    TICKETS_ISSUED = "tickets_issued", "Billets émis"
    PAYMENT_SUCCEEDED = "payment_succeeded", "Paiement confirmé"
    PAYMENT_FAILED = "payment_failed", "Paiement échoué"
    PAYMENT_REFUNDED = "payment_refunded", "Paiement remboursé"
    EVENT_REMINDER = "event_reminder", "Rappel d’événement"
    SYSTEM = "system", "Information système"


class DeliveryChannel(models.TextChoices):
    EMAIL = "email", "E-mail"
    SMS = "sms", "SMS"
    PUSH = "push", "Push"


class DeliveryStatus(models.TextChoices):
    QUEUED = "queued", "En attente"
    SENT = "sent", "Envoyé"
    FAILED = "failed", "Échoué"
    SKIPPED = "skipped", "Ignoré"


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="makolo_notifications",
    )
    kind = models.CharField(
        max_length=40,
        choices=NotificationKind.choices,
        default=NotificationKind.SYSTEM,
    )
    category = models.CharField(
        max_length=24,
        choices=NotificationCategory.choices,
        default=NotificationCategory.SYSTEM,
    )
    title = models.CharField(max_length=180)
    message = models.TextField()
    action_url = models.CharField(max_length=500, blank=True)
    dedup_key = models.CharField(max_length=255, unique=True, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at", "created_at"]),
            models.Index(fields=["category", "created_at"]),
        ]

    @property
    def is_read(self):
        return self.read_at is not None

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at", "updated_at"])
        return self

    def __str__(self):
        return f"{self.recipient} — {self.title}"


class NotificationDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    channel = models.CharField(max_length=16, choices=DeliveryChannel.choices)
    destination = models.CharField(max_length=255)
    status = models.CharField(
        max_length=16,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.QUEUED,
    )
    scheduled_for = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    provider_reference = models.CharField(max_length=255, blank=True)
    last_error = models.TextField(blank=True)
    skipped_reason = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_for", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "channel", "destination"],
                name="notification_delivery_unique_destination",
            )
        ]
        indexes = [
            models.Index(fields=["status", "scheduled_for"]),
            models.Index(fields=["channel", "status"]),
        ]

    def __str__(self):
        return f"{self.notification_id} — {self.channel} — {self.status}"
