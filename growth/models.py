import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class MarketingChannel(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp"
    INSTAGRAM = "instagram", "Instagram"
    FACEBOOK = "facebook", "Facebook"
    QR = "qr", "QR / Affiche"
    FLYER = "flyer", "Flyer"
    PARTNER = "partner", "Partenaire"
    EMAIL = "email", "E-mail"
    OTHER = "other", "Autre"


class MarketingAttributionStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    CONFIRMED = "confirmed", "Confirmée"
    REVERSED = "reversed", "Annulée"


class MarketingLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="marketing_links",
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="marketing_links",
    )
    crm_campaign = models.ForeignKey(
        "crm.CommunicationCampaign",
        on_delete=models.SET_NULL,
        related_name="marketing_links",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=160)
    channel = models.CharField(max_length=20, choices=MarketingChannel.choices)
    code = models.CharField(max_length=16, unique=True, blank=True)
    attribution_window_days = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(90)],
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_marketing_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "is_active"], name="growth_link_org_active_idx"),
            models.Index(fields=["event", "is_active"], name="growth_link_event_active_idx"),
            models.Index(fields=["channel", "created_at"], name="growth_link_channel_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.name = (self.name or "").strip()
        if not self.name:
            errors["name"] = "Le nom du lien est obligatoire."
        if self.event_id and self.event.organization_id != self.organization_id:
            errors["event"] = "L'événement doit appartenir à la même organisation."
        if self.crm_campaign_id and self.crm_campaign.organization_id != self.organization_id:
            errors["crm_campaign"] = "La campagne CRM doit appartenir à la même organisation."
        if self.crm_campaign_id and self.crm_campaign.event_id and self.crm_campaign.event_id != self.event_id:
            errors["crm_campaign"] = "Cette campagne CRM cible un autre événement."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.code:
            for _ in range(20):
                candidate = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:9]
                if candidate and not MarketingLink.objects.filter(code=candidate).exists():
                    self.code = candidate
                    break
            if not self.code:
                raise RuntimeError("Impossible de générer un code marketing unique.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization} — {self.name} ({self.code})"


class MarketingLinkVisit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    link = models.ForeignKey(MarketingLink, on_delete=models.CASCADE, related_name="visits")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="marketing_link_visits",
        null=True,
        blank=True,
    )
    session_key_hash = models.CharField(max_length=64, blank=True)
    referrer_domain = models.CharField(max_length=255, blank=True)
    visited_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-visited_at"]
        indexes = [
            models.Index(fields=["link", "visited_at"], name="growth_visit_link_time_idx"),
            models.Index(fields=["user", "visited_at"], name="growth_visit_user_time_idx"),
        ]

    def __str__(self):
        return f"{self.link.code} — {self.visited_at}"


class MarketingAttribution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "tickets.TicketOrder",
        on_delete=models.CASCADE,
        related_name="marketing_attribution",
    )
    link = models.ForeignKey(MarketingLink, on_delete=models.PROTECT, related_name="attributions")
    visit = models.ForeignKey(
        MarketingLinkVisit,
        on_delete=models.SET_NULL,
        related_name="attributions",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=MarketingAttributionStatus.choices,
        default=MarketingAttributionStatus.PENDING,
    )
    revenue_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3)
    attributed_at = models.DateTimeField(default=timezone.now)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-attributed_at"]
        indexes = [
            models.Index(fields=["link", "status", "attributed_at"], name="growth_attr_link_status_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.order_id:
            if self.order.event_id != self.link.event_id:
                errors["order"] = "La commande doit appartenir à l'événement du lien marketing."
            if self.order.event.organization_id != self.link.organization_id:
                errors["order"] = "La commande doit appartenir à l'organisation du lien marketing."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "").upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.link.code} → {self.order.reference}"


class EventFeedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="private_feedback",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_feedback",
    )
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="growth_feedback_event_user_uq")
        ]
        indexes = [
            models.Index(fields=["event", "rating"], name="growth_feedback_event_idx"),
        ]

    def __str__(self):
        return f"{self.event} — {self.rating}/5"
