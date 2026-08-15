import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class GrowthChannel(models.TextChoices):
    CRM = "crm", "CRM"
    PARTNERS = "partners", "Partenaires"
    PROMOTIONS = "promotions", "Promotions"
    LOYALTY = "loyalty", "Fidélité"
    OTHER = "other", "Autre"


class GrowthSpend(models.Model):
    """Dépense explicite utilisée pour les ratios Growth.

    Les revenus restent dérivés des sources de vérité métier. Une dépense est
    toujours conservée dans sa devise et n'est jamais convertie implicitement.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="growth_spends"
    )
    event = models.ForeignKey(
        "events.Event", on_delete=models.SET_NULL, related_name="growth_spends", null=True, blank=True
    )
    channel = models.CharField(max_length=20, choices=GrowthChannel.choices, default=GrowthChannel.OTHER)
    crm_campaign = models.ForeignKey(
        "crm.CommunicationCampaign", on_delete=models.SET_NULL, related_name="growth_spends", null=True, blank=True
    )
    partner_campaign = models.ForeignKey(
        "partners.AffiliateCampaign", on_delete=models.SET_NULL, related_name="growth_spends", null=True, blank=True
    )
    promotion = models.ForeignKey(
        "promotions.Promotion", on_delete=models.SET_NULL, related_name="growth_spends", null=True, blank=True
    )
    loyalty_program = models.ForeignKey(
        "loyalty.LoyaltyProgram", on_delete=models.SET_NULL, related_name="growth_spends", null=True, blank=True
    )
    label = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=3)
    incurred_at = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_growth_spends"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-incurred_at", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "channel", "incurred_at"], name="growth_spend_org_channel_idx"),
            models.Index(fields=["organization", "currency", "incurred_at"], name="growth_spend_org_currency_idx"),
            models.Index(fields=["event", "currency"], name="growth_spend_event_curr_idx"),
        ]

    def clean(self):
        super().clean()
        self.currency = (self.currency or "").strip().upper()
        self.label = (self.label or "").strip()
        errors = {}
        if len(self.currency) != 3:
            errors["currency"] = "Une devise ISO à trois lettres est requise."
        if not self.label:
            errors["label"] = "Le libellé de dépense est obligatoire."
        if self.event_id and self.event.organization_id != self.organization_id:
            errors["event"] = "L'événement doit appartenir à la même organisation."

        sources = [
            ("crm_campaign", self.crm_campaign, GrowthChannel.CRM),
            ("partner_campaign", self.partner_campaign, GrowthChannel.PARTNERS),
            ("promotion", self.promotion, GrowthChannel.PROMOTIONS),
            ("loyalty_program", self.loyalty_program, GrowthChannel.LOYALTY),
        ]
        selected = [(field, obj, channel) for field, obj, channel in sources if obj is not None]
        if len(selected) > 1:
            errors["channel"] = "Une dépense ne peut être rattachée qu'à une source Growth précise."
        elif selected:
            field, obj, expected_channel = selected[0]
            if self.channel != expected_channel:
                errors["channel"] = "Le canal doit correspondre à la source sélectionnée."
            if obj.organization_id != self.organization_id:
                errors[field] = "La source doit appartenir à la même organisation."
            source_event_id = getattr(obj, "event_id", None)
            if self.event_id and source_event_id and source_event_id != self.event_id:
                errors[field] = "La source concerne un autre événement."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "").strip().upper()
        self.label = (self.label or "").strip()
        super().save(*args, **kwargs)

    @property
    def source_label(self):
        source = self.crm_campaign or self.partner_campaign or self.promotion or self.loyalty_program
        return str(source) if source else self.get_channel_display()

    def __str__(self):
        return f"{self.organization} — {self.label} — {self.amount} {self.currency}"


class AnalyticsFact(models.Model):
    """Small idempotent projection of useful canonical Domain Events.

    Transactional dashboards remain sourced from canonical models. Facts exist
    for historical/event analysis only and deliberately do not duplicate the
    Domain Event payload or credential/person-sensitive data.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain_event = models.ForeignKey(
        "core.DomainEventOutbox", on_delete=models.CASCADE, related_name="analytics_facts"
    )
    fact_type = models.CharField(max_length=100)
    space = models.ForeignKey(
        "organizations.Organization", on_delete=models.SET_NULL,
        related_name="analytics_facts", null=True, blank=True,
    )
    activity = models.ForeignKey(
        "activities.Activity", on_delete=models.SET_NULL,
        related_name="analytics_facts", null=True, blank=True,
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence", on_delete=models.SET_NULL,
        related_name="analytics_facts", null=True, blank=True,
    )
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="analytics_facts", null=True, blank=True,
    )
    numeric_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["domain_event", "fact_type"], name="analytics_fact_event_type_unique"
            )
        ]
        indexes = [
            models.Index(fields=["space", "occurred_at"], name="analytics_fact_space_time_idx"),
            models.Index(fields=["activity", "occurred_at"], name="analytics_fact_act_time_idx"),
            models.Index(fields=["occurrence", "occurred_at"], name="analytics_fact_occ_time_idx"),
            models.Index(fields=["fact_type", "occurred_at"], name="analytics_fact_type_time_idx"),
        ]

    def __str__(self):
        return f"{self.fact_type} — {self.occurred_at:%Y-%m-%d %H:%M:%S}"
