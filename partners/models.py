import secrets
import string
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from events.models import Event
from organizations.models import Organization
from tickets.models import TicketOrder


class PartnerKind(models.TextChoices):
    AMBASSADOR = "ambassador", "Ambassadeur"
    INFLUENCER = "influencer", "Influenceur / Créateur"
    AGENCY = "agency", "Agence"
    MEDIA = "media", "Média"
    COMMUNITY = "community", "Communauté"
    BUSINESS = "business", "Entreprise / Partenaire"
    OTHER = "other", "Autre"


class PartnerStatus(models.TextChoices):
    INVITED = "invited", "Invité"
    ACTIVE = "active", "Actif"
    PAUSED = "paused", "En pause"
    CLOSED = "closed", "Clôturé"


class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    ACTIVE = "active", "Active"
    PAUSED = "paused", "En pause"
    ENDED = "ended", "Terminée"


class CommissionType(models.TextChoices):
    PERCENTAGE = "percentage", "Pourcentage"
    FIXED = "fixed", "Montant fixe"


class AttributionStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    CONFIRMED = "confirmed", "Confirmée"
    REVERSED = "reversed", "Annulée / inversée"


class CommissionStatus(models.TextChoices):
    EARNED = "earned", "Acquise"
    REVERSED = "reversed", "Annulée"
    PAID = "paid", "Payée"


class PayoutStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PAID = "paid", "Payé"
    CANCELLED = "cancelled", "Annulé"


class Partner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="partners")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="partner_profiles",
        null=True,
        blank=True,
        help_text="Compte Makolo lié au partenaire, si disponible.",
    )
    kind = models.CharField(max_length=24, choices=PartnerKind.choices, default=PartnerKind.AMBASSADOR)
    status = models.CharField(max_length=16, choices=PartnerStatus.choices, default=PartnerStatus.ACTIVE)
    name = models.CharField(max_length=180)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    public_label = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="partners_created",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                condition=models.Q(user__isnull=False),
                name="partner_unique_org_user",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status"], name="partner_org_status_idx"),
            models.Index(fields=["user", "status"], name="partner_user_status_idx"),
        ]

    def clean(self):
        super().clean()
        self.email = (self.email or "").strip().lower()
        if self.user_id and self.email and self.user.email and self.user.email.lower() != self.email:
            raise ValidationError({"email": "L’e-mail doit correspondre au compte Makolo lié."})
        if not self.name.strip():
            raise ValidationError({"name": "Le nom du partenaire est obligatoire."})

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.public_label.strip() or self.name

    def __str__(self):
        return f"{self.name} — {self.organization.name}"


class AffiliateCampaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="affiliate_campaigns")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="affiliate_campaigns")
    name = models.CharField(max_length=180)
    status = models.CharField(max_length=16, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT)
    commission_type = models.CharField(max_length=16, choices=CommissionType.choices, default=CommissionType.PERCENTAGE)
    commission_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    commission_currency = models.CharField(max_length=3, default="USD")
    attribution_window_days = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(90)],
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="affiliate_campaigns_created",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "event", "name"], name="affiliate_campaign_unique_name"),
        ]
        indexes = [
            models.Index(fields=["organization", "status"], name="affiliate_campaign_org_idx"),
            models.Index(fields=["event", "status"], name="affiliate_campaign_event_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.commission_currency = (self.commission_currency or "USD").upper()
        if self.event_id and self.organization_id and self.event.organization_id != self.organization_id:
            errors["event"] = "L’événement doit appartenir à l’organisation de la campagne."
        if self.commission_type == CommissionType.PERCENTAGE and self.commission_value > 100:
            errors["commission_value"] = "Le pourcentage de commission ne peut pas dépasser 100 %."
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "La fin de campagne doit être postérieure au début."
        if len(self.commission_currency) != 3:
            errors["commission_currency"] = "La devise doit contenir exactement 3 lettres."
        if errors:
            raise ValidationError(errors)

    @property
    def is_active_now(self):
        now = timezone.now()
        if self.status != CampaignStatus.ACTIVE:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True

    def __str__(self):
        return f"{self.name} — {self.event.title}"


class ReferralCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(AffiliateCampaign, on_delete=models.CASCADE, related_name="referral_codes")
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name="referral_codes")
    code = models.CharField(max_length=40, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    commission_type_override = models.CharField(max_length=16, choices=CommissionType.choices, blank=True)
    commission_value_override = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["partner__name", "code"]
        constraints = [
            models.UniqueConstraint(fields=["campaign", "partner"], name="referral_code_unique_campaign_partner"),
        ]
        indexes = [
            models.Index(fields=["code", "is_active"], name="referral_code_lookup_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.campaign_id and self.partner_id and self.campaign.organization_id != self.partner.organization_id:
            errors["partner"] = "Le partenaire doit appartenir à la même organisation que la campagne."
        effective_type = self.commission_type_override or self.campaign.commission_type
        effective_value = self.commission_value_override
        if effective_value is not None and effective_type == CommissionType.PERCENTAGE and effective_value > 100:
            errors["commission_value_override"] = "Le pourcentage de commission ne peut pas dépasser 100 %."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.code:
            alphabet = string.ascii_uppercase + string.digits
            while True:
                candidate = "MK-" + "".join(secrets.choice(alphabet) for _ in range(8))
                if not ReferralCode.objects.filter(code=candidate).exists():
                    self.code = candidate
                    break
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    @property
    def effective_commission_type(self):
        return self.commission_type_override or self.campaign.commission_type

    @property
    def effective_commission_value(self):
        return self.commission_value_override if self.commission_value_override is not None else self.campaign.commission_value

    @property
    def is_usable(self):
        return self.is_active and self.partner.status == PartnerStatus.ACTIVE and self.campaign.is_active_now

    def __str__(self):
        return f"{self.code} — {self.partner.display_name}"


class ReferralVisit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral_code = models.ForeignKey(ReferralCode, on_delete=models.CASCADE, related_name="visits")
    visitor_id = models.UUIDField()
    landing_path = models.CharField(max_length=255, blank=True)
    referrer_domain = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["referral_code", "visitor_id"], name="referral_visit_unique_visitor_code"),
        ]
        indexes = [
            models.Index(fields=["referral_code", "created_at"], name="referral_visit_code_time_idx"),
        ]

    def __str__(self):
        return f"{self.referral_code.code} — {self.created_at:%Y-%m-%d}"


class ReferralAttribution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(TicketOrder, on_delete=models.CASCADE, related_name="referral_attribution")
    referral_code = models.ForeignKey(ReferralCode, on_delete=models.PROTECT, related_name="attributions")
    campaign = models.ForeignKey(AffiliateCampaign, on_delete=models.PROTECT, related_name="attributions")
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="attributions")
    visitor_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=AttributionStatus.choices, default=AttributionStatus.PENDING)
    attributed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-attributed_at"]
        indexes = [
            models.Index(fields=["campaign", "status", "attributed_at"], name="ref_attr_campaign_idx"),
            models.Index(fields=["partner", "status", "attributed_at"], name="ref_attr_partner_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.order_id and self.campaign_id and self.order.event_id != self.campaign.event_id:
            errors["order"] = "La commande ne correspond pas à l’événement de la campagne."
        if self.referral_code_id and self.partner_id and self.referral_code.partner_id != self.partner_id:
            errors["partner"] = "Le partenaire doit correspondre au code de parrainage."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.order.reference} — {self.partner.display_name}"


class PartnerPayout(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="partner_payouts")
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="payouts")
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=16, choices=PayoutStatus.choices, default=PayoutStatus.DRAFT)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="partner_payouts_created",
        null=True,
        blank=True,
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="partner_payouts_paid",
        null=True,
        blank=True,
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status", "created_at"], name="partner_payout_org_idx"),
            models.Index(fields=["partner", "currency", "status"], name="partner_payout_partner_idx"),
        ]

    def clean(self):
        super().clean()
        self.currency = self.currency.upper()
        if self.partner_id and self.organization_id and self.partner.organization_id != self.organization_id:
            raise ValidationError({"partner": "Le partenaire n’appartient pas à cette organisation."})

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "").upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.partner.display_name} — {self.amount} {self.currency}"


class PartnerCommission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attribution = models.OneToOneField(ReferralAttribution, on_delete=models.CASCADE, related_name="commission")
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="commissions")
    campaign = models.ForeignKey(AffiliateCampaign, on_delete=models.PROTECT, related_name="commissions")
    order = models.ForeignKey(TicketOrder, on_delete=models.PROTECT, related_name="partner_commissions")
    payout = models.ForeignKey(PartnerPayout, on_delete=models.SET_NULL, related_name="commissions", null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    currency = models.CharField(max_length=3)
    commission_type = models.CharField(max_length=16, choices=CommissionType.choices)
    commission_value = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=CommissionStatus.choices, default=CommissionStatus.EARNED)
    earned_at = models.DateTimeField(default=timezone.now)
    reversed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-earned_at"]
        indexes = [
            models.Index(fields=["partner", "status", "currency"], name="partner_comm_partner_idx"),
            models.Index(fields=["campaign", "status", "earned_at"], name="partner_comm_campaign_idx"),
        ]

    def clean(self):
        super().clean()
        if self.partner_id and self.campaign_id and self.partner.organization_id != self.campaign.organization_id:
            raise ValidationError({"partner": "Le partenaire et la campagne doivent appartenir à la même organisation."})

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "USD").upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.partner.display_name} — {self.amount} {self.currency}"
