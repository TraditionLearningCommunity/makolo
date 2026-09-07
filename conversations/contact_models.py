import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .audience_models import ConversationAudienceSet
from .core_models import Conversation


class ContactPolicyMode(models.TextChoices):
    CLOSED = "closed", "Contact fermé"
    REQUEST = "request", "Sur demande"
    CONTEXTUAL = "contextual", "Direct dans un contexte légitime"
    DIRECT = "direct", "Contact direct autorisé"


class ContactIntent(models.TextChoices):
    ACTIVITY = "activity", "Parler d’une activité"
    COLLABORATION = "collaboration", "Proposer une collaboration"
    QUESTION = "question", "Demander une information"
    OTHER = "other", "Autre raison"


class ContactRequestStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ACCEPTED = "accepted", "Acceptée"
    DECLINED = "declined", "Refusée"
    CANCELLED = "cancelled", "Annulée"
    EXPIRED = "expired", "Expirée"


class CommunicationEndpointProvider(models.TextChoices):
    TELEGRAM = "telegram", "Telegram"
    VIBER = "viber", "Viber"
    MESSENGER = "messenger", "Messenger"
    WHATSAPP = "whatsapp", "WhatsApp"
    OTHER = "other", "Autre"


class CommunicationEndpointVisibility(models.TextChoices):
    PRIVATE = "private", "Privé"
    CONTEXTUAL = "contextual", "Contextuel"
    PUBLIC = "public", "Public"


class CommunicationEndpointStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    RETIRED = "retired", "Retiré"


class CommunicationRouteProvider(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp"
    TELEGRAM = "telegram", "Telegram"
    MESSENGER = "messenger", "Messenger"
    VIBER = "viber", "Viber"
    SMS = "sms", "SMS"
    EMAIL = "email", "E-mail"
    PHONE = "phone", "Téléphone"
    OTHER = "other", "Autre"


class CommunicationRouteDestinationKind(models.TextChoices):
    GROUP_INVITE = "group_invite", "Invitation de groupe"
    DIRECT = "direct", "Contact direct"
    THREAD = "thread", "Fil"
    CHANNEL = "channel", "Canal"
    PHONE = "phone", "Téléphone"
    EMAIL = "email", "E-mail"
    HANDLE = "handle", "Identifiant"
    URL = "url", "Lien"


class CommunicationRouteStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    RETIRED = "retired", "Retirée"


class ProfileContactPolicy(models.Model):
    profile = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contact_policy")
    mode = models.CharField(max_length=16, choices=ContactPolicyMode.choices, default=ContactPolicyMode.REQUEST)
    allow_activity_context = models.BooleanField(default=True)
    allow_space_context = models.BooleanField(default=True)
    allow_action_proposal_context = models.BooleanField(default=True)
    allow_other_requests = models.BooleanField(default=False)
    valid_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ContactRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sent_contact_requests")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="received_contact_requests")
    intent = models.CharField(max_length=24, choices=ContactIntent.choices)
    message = models.CharField(max_length=500)
    status = models.CharField(max_length=16, choices=ContactRequestStatus.choices, default=ContactRequestStatus.PENDING)
    expires_at = models.DateTimeField(null=True, blank=True)
    client_reference = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=~Q(sender=models.F("recipient")), name="conv_contact_distinct_profiles"),
            models.UniqueConstraint(fields=["sender", "recipient", "intent"], condition=Q(status=ContactRequestStatus.PENDING), name="conv_contact_pending_unique"),
            models.UniqueConstraint(fields=["client_reference"], condition=Q(client_reference__isnull=False), name="conv_contact_client_ref_unique"),
        ]
        indexes = [
            models.Index(fields=["recipient", "status", "created_at"], name="conv_contact_recipient_idx"),
            models.Index(fields=["sender", "status", "created_at"], name="conv_contact_sender_idx"),
        ]

    def clean(self):
        super().clean()
        self.message = (self.message or "").strip()
        self.client_reference = (self.client_reference or "").strip() or None
        errors = {}
        if self.sender_id and self.sender_id == self.recipient_id:
            errors["recipient"] = "Un Profile ne se contacte pas lui-même."
        if not self.message:
            errors["message"] = "Une demande de contact doit expliquer son intention."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class AdditionalCommunicationEndpoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="additional_communication_endpoints", null=True, blank=True)
    space = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="additional_communication_endpoints", null=True, blank=True)
    provider = models.CharField(max_length=24, choices=CommunicationEndpointProvider.choices)
    destination_kind = models.CharField(max_length=32)
    value = models.CharField(max_length=500)
    label = models.CharField(max_length=120, blank=True)
    visibility = models.CharField(max_length=16, choices=CommunicationEndpointVisibility.choices, default=CommunicationEndpointVisibility.PRIVATE)
    status = models.CharField(max_length=16, choices=CommunicationEndpointStatus.choices, default=CommunicationEndpointStatus.ACTIVE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_additional_communication_endpoints")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(profile__isnull=False, space__isnull=True) | Q(profile__isnull=True, space__isnull=False)), name="conv_endpoint_single_owner"),
        ]
        indexes = [models.Index(fields=["provider", "status"], name="conv_endpoint_provider_idx")]

    def clean(self):
        super().clean()
        self.value = (self.value or "").strip()
        self.label = (self.label or "").strip()
        if bool(self.profile_id) == bool(self.space_id):
            raise ValidationError("Un endpoint appartient exactement à un Profile ou un Space.")
        if not self.value:
            raise ValidationError({"value": "La destination est obligatoire."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CommunicationRoute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="communication_routes")
    provider = models.CharField(max_length=24, choices=CommunicationRouteProvider.choices)
    destination_kind = models.CharField(max_length=24, choices=CommunicationRouteDestinationKind.choices)
    label = models.CharField(max_length=160)
    purpose = models.CharField(max_length=300, blank=True)
    destination = models.CharField(max_length=700)
    audience = models.ForeignKey(ConversationAudienceSet, on_delete=models.PROTECT, related_name="communication_routes", null=True, blank=True)
    status = models.CharField(max_length=16, choices=CommunicationRouteStatus.choices, default=CommunicationRouteStatus.ACTIVE)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_communication_routes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["conversation", "status"], name="conv_route_conv_status_idx")]

    def clean(self):
        super().clean()
        self.label = (self.label or "").strip()
        self.purpose = (self.purpose or "").strip()
        self.destination = (self.destination or "").strip()
        errors = {}
        if not self.label:
            errors["label"] = "Une route doit avoir un libellé compréhensible."
        if not self.destination:
            errors["destination"] = "Une destination est obligatoire."
        if self.audience_id and self.conversation_id and self.audience.conversation_id != self.conversation_id:
            errors["audience"] = "L’audience de la route doit appartenir à la même Conversation."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
