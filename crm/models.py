import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class ContactSource(models.TextChoices):
    TICKET_ORDER = "ticket_order", "Commande"
    TICKET = "ticket", "Billet"
    WAITLIST = "waitlist", "Liste d’attente"
    FOLLOWER = "follower", "Abonné organisateur"
    MANUAL = "manual", "Manuel"


class MarketingConsent(models.TextChoices):
    UNKNOWN = "unknown", "Non renseigné"
    SUBSCRIBED = "subscribed", "Abonné"
    UNSUBSCRIBED = "unsubscribed", "Désabonné"


class AudienceKind(models.TextChoices):
    ALL = "all", "Tous les contacts"
    FOLLOWERS = "followers", "Abonnés de l’organisateur"
    CONFIRMED_BUYERS = "confirmed_buyers", "Acheteurs confirmés"
    TICKET_HOLDERS = "ticket_holders", "Détenteurs de billets"
    ATTENDEES = "attendees", "Participants présents"
    NO_SHOWS = "no_shows", "Absents / no-show"
    WAITLIST = "waitlist", "Liste d’attente"
    PARTNER_REFERRED = "partner_referred", "Acquisition partenaire"


class CommunicationKind(models.TextChoices):
    MARKETING = "marketing", "Marketing"
    EVENT_UPDATE = "event_update", "Information événement"


class CommunicationCampaignStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    SCHEDULED = "scheduled", "Planifiée"
    SENDING = "sending", "En cours"
    SENT = "sent", "Envoyée"
    CANCELLED = "cancelled", "Annulée"


class CampaignRecipientStatus(models.TextChoices):
    QUEUED = "queued", "En attente"
    PROCESSING = "processing", "En cours"
    SENT = "sent", "Envoyé"
    FAILED = "failed", "Échoué"
    SKIPPED = "skipped", "Ignoré"


class CustomFieldType(models.TextChoices):
    TEXT = "text", "Texte"
    NUMBER = "number", "Nombre"
    BOOLEAN = "boolean", "Oui / Non"
    DATE = "date", "Date"
    SELECT = "select", "Liste de choix"


class CampaignAttributionStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    CONFIRMED = "confirmed", "Conversion confirmée"
    REVERSED = "reversed", "Conversion annulée"


class CRMContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="crm_contacts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="crm_contact_profiles",
        null=True,
        blank=True,
    )
    email = models.EmailField()
    name = models.CharField(max_length=180, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    source = models.CharField(
        max_length=24,
        choices=ContactSource.choices,
        default=ContactSource.TICKET_ORDER,
    )
    marketing_consent = models.CharField(
        max_length=16,
        choices=MarketingConsent.choices,
        default=MarketingConsent.UNKNOWN,
    )
    consent_source = models.CharField(max_length=120, blank=True)
    consent_updated_at = models.DateTimeField(null=True, blank=True)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "email"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                name="crm_contact_org_email_unique",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "marketing_consent"], name="crm_contact_consent_idx"),
            models.Index(fields=["organization", "last_seen_at"], name="crm_contact_seen_idx"),
            models.Index(fields=["user", "organization"], name="crm_contact_user_org_idx"),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        self.name = (self.name or "").strip()
        self.phone = (self.phone or "").strip()
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.name or self.email

    def __str__(self):
        return f"{self.organization} — {self.display_name}"


class CRMTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="crm_tags",
    )
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=24, default="indigo")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_crm_tags",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="crm_tag_org_name_unique")
        ]

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        self.color = (self.color or "indigo").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization} — {self.name}"


class CRMContactTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(CRMContact, on_delete=models.CASCADE, related_name="tag_links")
    tag = models.ForeignKey(CRMTag, on_delete=models.CASCADE, related_name="contact_links")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_crm_tags",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["contact", "tag"], name="crm_contact_tag_unique")
        ]
        indexes = [models.Index(fields=["tag", "contact"], name="crm_contact_tag_lookup_idx")]

    def clean(self):
        super().clean()
        if self.contact_id and self.tag_id and self.contact.organization_id != self.tag.organization_id:
            raise ValidationError("Le tag et le contact doivent appartenir à la même organisation.")

    def __str__(self):
        return f"{self.contact} — {self.tag.name}"


class CRMCustomField(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="crm_custom_fields",
    )
    key = models.SlugField(max_length=80)
    label = models.CharField(max_length=120)
    field_type = models.CharField(max_length=16, choices=CustomFieldType.choices, default=CustomFieldType.TEXT)
    options = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_crm_custom_fields",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["label"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "key"], name="crm_custom_field_org_key_unique")
        ]

    def clean(self):
        super().clean()
        if self.field_type == CustomFieldType.SELECT:
            if not isinstance(self.options, list) or not [item for item in self.options if str(item).strip()]:
                raise ValidationError({"options": "Une liste de choix nécessite au moins une option."})
        elif self.options not in (None, [], {}):
            self.options = []

    def __str__(self):
        return f"{self.organization} — {self.label}"


class CRMContactFieldValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(CRMContact, on_delete=models.CASCADE, related_name="custom_values")
    field = models.ForeignKey(CRMCustomField, on_delete=models.CASCADE, related_name="contact_values")
    value = models.JSONField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_crm_custom_values",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["contact", "field"], name="crm_contact_field_value_unique")
        ]
        indexes = [models.Index(fields=["field", "contact"], name="crm_field_value_lookup_idx")]

    def clean(self):
        super().clean()
        if self.contact_id and self.field_id and self.contact.organization_id != self.field.organization_id:
            raise ValidationError("Le champ et le contact doivent appartenir à la même organisation.")

    def __str__(self):
        return f"{self.contact} — {self.field.label}"


class AudienceSegment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="crm_segments",
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="crm_segments",
        null=True,
        blank=True,
    )
    ticket_type = models.ForeignKey(
        "tickets.TicketType",
        on_delete=models.SET_NULL,
        related_name="crm_segments",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    audience_kind = models.CharField(
        max_length=32,
        choices=AudienceKind.choices,
        default=AudienceKind.ALL,
    )
    marketing_consent_only = models.BooleanField(default=False)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    required_tags = models.ManyToManyField(CRMTag, blank=True, related_name="segments")
    custom_filters = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_crm_segments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="crm_segment_org_name_unique",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "is_active"], name="crm_segment_org_active_idx"),
            models.Index(fields=["event", "audience_kind"], name="crm_segment_event_kind_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.event_id and self.event.organization_id != self.organization_id:
            errors["event"] = "L’événement doit appartenir à la même organisation."
        if self.audience_kind not in {AudienceKind.ALL, AudienceKind.FOLLOWERS} and not self.event_id:
            errors["event"] = "Ce type d’audience nécessite un événement."
        if self.ticket_type_id:
            if not self.event_id:
                errors["ticket_type"] = "Choisissez d’abord un événement."
            elif self.ticket_type.event_id != self.event_id:
                errors["ticket_type"] = "Le type de billet doit appartenir à l’événement du segment."
        if not isinstance(self.custom_filters, dict):
            errors["custom_filters"] = "Les filtres de champs personnalisés doivent former un objet clé/valeur."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.organization} — {self.name}"


class CampaignTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="crm_campaign_templates",
    )
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=20, choices=CommunicationKind.choices, default=CommunicationKind.MARKETING)
    subject = models.CharField(max_length=180)
    preview_text = models.CharField(max_length=220, blank=True)
    body = models.TextField()
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    use_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_crm_campaign_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="crm_template_org_name_unique")
        ]

    def clean(self):
        super().clean()
        if bool(self.cta_label) != bool(self.cta_url):
            raise ValidationError({"cta_url": "Le libellé et le lien d’action doivent être fournis ensemble."})

    def __str__(self):
        return f"{self.organization} — {self.name}"


class CommunicationCampaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="crm_campaigns",
    )
    segment = models.ForeignKey(
        AudienceSegment,
        on_delete=models.PROTECT,
        related_name="campaigns",
    )
    template = models.ForeignKey(
        CampaignTemplate,
        on_delete=models.SET_NULL,
        related_name="campaigns",
        null=True,
        blank=True,
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.SET_NULL,
        related_name="crm_campaigns",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=160)
    kind = models.CharField(
        max_length=20,
        choices=CommunicationKind.choices,
        default=CommunicationKind.MARKETING,
    )
    subject = models.CharField(max_length=180)
    preview_text = models.CharField(max_length=220, blank=True)
    body = models.TextField()
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.URLField(blank=True)
    track_conversions = models.BooleanField(default=True)
    attribution_window_days = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(90)],
    )
    status = models.CharField(
        max_length=16,
        choices=CommunicationCampaignStatus.choices,
        default=CommunicationCampaignStatus.DRAFT,
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_crm_campaigns",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status", "created_at"], name="crm_campaign_org_status_idx"),
            models.Index(fields=["status", "scheduled_at"], name="crm_campaign_due_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.segment_id and self.segment.organization_id != self.organization_id:
            errors["segment"] = "Le segment doit appartenir à la même organisation."
        if self.template_id and self.template.organization_id != self.organization_id:
            errors["template"] = "Le modèle doit appartenir à la même organisation."
        if self.event_id and self.event.organization_id != self.organization_id:
            errors["event"] = "L’événement doit appartenir à la même organisation."
        if self.segment_id and self.segment.event_id and self.event_id and self.segment.event_id != self.event_id:
            errors["event"] = "L’événement doit correspondre à celui du segment."
        if self.kind == CommunicationKind.EVENT_UPDATE and not self.event_id:
            errors["event"] = "Une communication événementielle nécessite un événement."
        if bool(self.cta_label) != bool(self.cta_url):
            errors["cta_url"] = "Le libellé et le lien d’action doivent être fournis ensemble."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.organization} — {self.name}"


class CampaignRecipient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        CommunicationCampaign,
        on_delete=models.CASCADE,
        related_name="recipients",
    )
    contact = models.ForeignKey(
        CRMContact,
        on_delete=models.PROTECT,
        related_name="campaign_recipients",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="crm_campaign_recipients",
        null=True,
        blank=True,
    )
    email = models.EmailField()
    name = models.CharField(max_length=180, blank=True)
    status = models.CharField(
        max_length=16,
        choices=CampaignRecipientStatus.choices,
        default=CampaignRecipientStatus.QUEUED,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    scheduled_for = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True)
    skipped_reason = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)
    first_clicked_at = models.DateTimeField(null=True, blank=True)
    last_clicked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "contact"],
                name="crm_recipient_campaign_contact_unique",
            )
        ]
        indexes = [
            models.Index(fields=["status", "scheduled_for"], name="crm_recipient_due_idx"),
            models.Index(fields=["campaign", "status"], name="crm_recipient_campaign_idx"),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.campaign} — {self.email} — {self.status}"


class CampaignAttribution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "tickets.TicketOrder",
        on_delete=models.CASCADE,
        related_name="crm_campaign_attribution",
    )
    campaign = models.ForeignKey(
        CommunicationCampaign,
        on_delete=models.PROTECT,
        related_name="attributions",
    )
    recipient = models.ForeignKey(
        CampaignRecipient,
        on_delete=models.SET_NULL,
        related_name="attributions",
        null=True,
        blank=True,
    )
    contact = models.ForeignKey(
        CRMContact,
        on_delete=models.SET_NULL,
        related_name="campaign_attributions",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=CampaignAttributionStatus.choices,
        default=CampaignAttributionStatus.PENDING,
    )
    revenue_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-captured_at"]
        indexes = [
            models.Index(fields=["campaign", "status", "captured_at"], name="crm_attr_campaign_status_idx")
        ]

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "").upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.campaign} — {self.order} — {self.status}"


class CRMContactNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(CRMContact, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="crm_contact_notes",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["contact", "created_at"], name="crm_note_contact_idx")]

    def __str__(self):
        return f"{self.contact} — {self.author}"
