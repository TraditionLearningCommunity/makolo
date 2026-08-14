import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .models import CRMContact


class CRMInteractionType(models.TextChoices):
    JOURNEY_SUBMITTED = "journey.submitted", "Démarche soumise"
    JOURNEY_CONFIRMED = "journey.confirmed", "Démarche confirmée"
    JOURNEY_FULFILLED = "journey.fulfilled", "Démarche réalisée"
    ACCESS_ISSUED = "access.issued", "Accès émis"
    ACCESS_USED = "access.used", "Accès utilisé"
    COMMERCE_ORDER_CONFIRMED = "commerce.order.confirmed", "Commande confirmée"
    PAYMENT_SUCCEEDED = "payment.succeeded", "Paiement réussi"
    GROUP_MEMBERSHIP_ACTIVE = "group.membership.active", "Membre d’un Groupe"
    LEGACY_EVENT = "legacy.event", "Interaction Event historique"


class AudienceStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archivée"


class AudienceMemberSource(models.TextChoices):
    MANUAL = "manual", "Ajout manuel"
    GROUP = "group", "Groupe"
    GROUP_SNAPSHOT = "group_snapshot", "Snapshot de Groupe"


# CRMContact remains the historical public model name. Its canonical identity is
# organization + Profile whenever a Profile exists; email uniqueness continues
# to protect legacy guest contacts that do not have a Profile.
_profile_constraint = models.UniqueConstraint(
    fields=["organization", "user"],
    condition=Q(user__isnull=False),
    name="crm_contact_org_profile_unique",
)
if not any(constraint.name == _profile_constraint.name for constraint in CRMContact._meta.constraints):
    CRMContact._meta.constraints.append(_profile_constraint)


class CRMInteraction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(CRMContact, on_delete=models.CASCADE, related_name="interactions")
    domain_event = models.ForeignKey(
        "core.DomainEventOutbox",
        on_delete=models.SET_NULL,
        related_name="crm_interactions",
        null=True,
        blank=True,
    )
    interaction_type = models.CharField(max_length=48, choices=CRMInteractionType.choices)
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.SET_NULL,
        related_name="crm_interactions",
        null=True,
        blank=True,
    )
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["contact", "domain_event", "interaction_type"],
                condition=Q(domain_event__isnull=False),
                name="crm_interaction_event_type_unique",
            )
        ]
        indexes = [
            models.Index(fields=["contact", "occurred_at"], name="crm_interaction_contact_date_idx"),
            models.Index(fields=["domain_event"], name="crm_interaction_event_idx"),
        ]

    def __str__(self):
        return f"{self.contact} — {self.interaction_type}"


class Audience(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="crm_audiences",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=AudienceStatus.choices, default=AudienceStatus.ACTIVE)
    source_group = models.ForeignKey(
        "groups.Group",
        on_delete=models.SET_NULL,
        related_name="crm_audiences",
        null=True,
        blank=True,
    )
    source_snapshot = models.ForeignKey(
        "groups.GroupSnapshot",
        on_delete=models.SET_NULL,
        related_name="crm_audiences",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_crm_audiences",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="crm_audience_org_name_unique")
        ]
        indexes = [models.Index(fields=["organization", "status"], name="crm_audience_org_status_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.source_group_id:
            if self.source_group.owner_profile_id:
                errors["source_group"] = "Un Groupe personnel ne peut pas alimenter le CRM d’un Espace."
            elif self.source_group.space_id != self.organization_id:
                errors["source_group"] = "Le Groupe doit appartenir au même Espace que l’Audience."
        if self.source_snapshot_id:
            snapshot_group = self.source_snapshot.group
            if snapshot_group.owner_profile_id:
                errors["source_snapshot"] = "Un snapshot de Groupe personnel ne peut pas alimenter le CRM."
            elif snapshot_group.space_id != self.organization_id:
                errors["source_snapshot"] = "Le snapshot doit appartenir au même Espace que l’Audience."
            if self.source_group_id and self.source_snapshot.group_id != self.source_group_id:
                errors["source_snapshot"] = "Le snapshot doit provenir du Groupe source de l’Audience."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.organization} — {self.name}"


class AudienceMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audience = models.ForeignKey(Audience, on_delete=models.CASCADE, related_name="members")
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="crm_audience_memberships",
    )
    source = models.CharField(
        max_length=24,
        choices=AudienceMemberSource.choices,
        default=AudienceMemberSource.MANUAL,
    )
    source_group = models.ForeignKey(
        "groups.Group",
        on_delete=models.SET_NULL,
        related_name="crm_audience_members",
        null=True,
        blank=True,
    )
    source_snapshot = models.ForeignKey(
        "groups.GroupSnapshot",
        on_delete=models.SET_NULL,
        related_name="crm_audience_members",
        null=True,
        blank=True,
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["profile__email"]
        constraints = [
            models.UniqueConstraint(fields=["audience", "profile"], name="crm_audience_member_unique")
        ]
        indexes = [models.Index(fields=["profile"], name="crm_audience_member_profile_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.source_group_id:
            if self.source_group.owner_profile_id or self.source_group.space_id != self.audience.organization_id:
                errors["source_group"] = "Le Groupe source doit appartenir à l’Espace de l’Audience."
        if self.source_snapshot_id:
            group = self.source_snapshot.group
            if group.owner_profile_id or group.space_id != self.audience.organization_id:
                errors["source_snapshot"] = "Le snapshot source doit appartenir à l’Espace de l’Audience."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.audience} — {self.profile}"
