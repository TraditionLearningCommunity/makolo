import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ShareIntent(models.TextChoices):
    VIEW = "view", "Voir"
    PARTICIPATE = "participate", "Participer"
    START_JOURNEY = "start_journey", "Commencer"


class ShareStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    REVOKED = "revoked", "Révoqué"
    EXPIRED = "expired", "Expiré"


class ShareSubjectType(models.TextChoices):
    ACTIVITY = "activity", "Activity"
    OPPORTUNITY = "opportunity", "Opportunity"
    JOURNEY = "journey", "Journey"


class ShareEnvelope(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="share_envelopes_created",
        null=True,
        blank=True,
    )
    subject_type = models.CharField(max_length=24, choices=ShareSubjectType.choices)
    intent = models.CharField(max_length=24, choices=ShareIntent.choices, default=ShareIntent.VIEW)
    status = models.CharField(max_length=16, choices=ShareStatus.choices, default=ShareStatus.ACTIVE)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="sharing_env_status_created_idx"),
            models.Index(fields=["expires_at"], name="sharing_env_expires_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.status == ShareStatus.REVOKED and not self.revoked_at:
            errors["revoked_at"] = "Un partage révoqué doit conserver sa date de révocation."
        if self.status != ShareStatus.REVOKED and self.revoked_at:
            errors["status"] = "Une date de révocation exige le statut révoqué."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def effective_status_at(self, at=None):
        at = at or timezone.now()
        if self.status == ShareStatus.REVOKED:
            return ShareStatus.REVOKED
        if self.status == ShareStatus.EXPIRED or (self.expires_at and self.expires_at <= at):
            return ShareStatus.EXPIRED
        return ShareStatus.ACTIVE

    @property
    def effective_status(self):
        return self.effective_status_at()

    def is_active_at(self, at=None):
        return self.effective_status_at(at) == ShareStatus.ACTIVE

    def __str__(self):
        return f"{self.get_subject_type_display()} · {self.get_intent_display()}"


class ShareLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    envelope = models.OneToOneField(ShareEnvelope, on_delete=models.CASCADE, related_name="link")
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    @property
    def token_fingerprint(self):
        return f"{self.token_hash[:12]}…"

    def __str__(self):
        return f"ShareLink {self.token_fingerprint}"


class ShareDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    envelope = models.ForeignKey(
        ShareEnvelope,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    recipient = models.ForeignKey(
        "accounts.UserProfile",
        on_delete=models.CASCADE,
        related_name="share_deliveries_received",
    )
    delivered_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-delivered_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["envelope", "recipient"],
                name="sharing_delivery_unique_recipient",
            ),
            models.CheckConstraint(
                condition=models.Q(accepted_at__isnull=True) | models.Q(declined_at__isnull=True),
                name="sharing_delivery_not_accept_and_decline",
            ),
        ]
        indexes = [
            models.Index(fields=["recipient", "delivered_at"], name="sharing_delivery_recipient_idx"),
        ]

    def clean(self):
        super().clean()
        if self.accepted_at and self.declined_at:
            raise ValidationError("Un partage ne peut pas être accepté et ignoré à la fois.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.envelope} → {self.recipient}"


class ActivityShareSubject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    envelope = models.OneToOneField(
        ShareEnvelope,
        on_delete=models.CASCADE,
        related_name="activity_subject",
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.SET_NULL,
        related_name="share_subjects",
        null=True,
        blank=True,
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.SET_NULL,
        related_name="share_subjects",
        null=True,
        blank=True,
    )

    def clean(self):
        super().clean()
        errors = {}
        if self.envelope_id and self.envelope.subject_type != ShareSubjectType.ACTIVITY:
            errors["envelope"] = "L’enveloppe doit cibler une Activity."
        if self.occurrence_id and self.activity_id and self.occurrence.activity_id != self.activity_id:
            errors["occurrence"] = "L’Occurrence doit appartenir à l’Activity partagée."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return str(self.activity or "Activity indisponible")


class OpportunityShareSubject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    envelope = models.OneToOneField(
        ShareEnvelope,
        on_delete=models.CASCADE,
        related_name="opportunity_subject",
    )
    opportunity_revision = models.ForeignKey(
        "opportunities.OpportunityRevision",
        on_delete=models.SET_NULL,
        related_name="share_subjects",
        null=True,
        blank=True,
    )

    def clean(self):
        super().clean()
        if self.envelope_id and self.envelope.subject_type != ShareSubjectType.OPPORTUNITY:
            raise ValidationError({"envelope": "L’enveloppe doit cibler une Opportunity."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return str(self.opportunity_revision or "Opportunity indisponible")


class JourneyShareSubject(models.Model):
    """Immutable, allowlist-first transport projection for a reusable Journey share."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    envelope = models.OneToOneField(
        ShareEnvelope,
        on_delete=models.CASCADE,
        related_name="journey_subject",
    )
    source_journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.SET_NULL,
        related_name="share_subjects",
        null=True,
        blank=True,
    )
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    def clean(self):
        super().clean()
        errors = {}
        if self.envelope_id and self.envelope.subject_type != ShareSubjectType.JOURNEY:
            errors["envelope"] = "L’enveloppe doit cibler une Journey."
        if not isinstance(self.snapshot, dict):
            errors["snapshot"] = "Le snapshot Journey doit être un objet JSON structuré."
        elif self.snapshot.get("schema_version") != 1:
            errors["snapshot"] = "Version de snapshot Journey non supportée."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = JourneyShareSubject.objects.filter(pk=self.pk).values(
                "envelope_id", "source_journey_id", "snapshot"
            ).first()
            current = {
                "envelope_id": self.envelope_id,
                "source_journey_id": self.source_journey_id,
                "snapshot": self.snapshot,
            }
            if previous and previous != current:
                raise ValidationError("Un snapshot Journey partagé est immuable. Créez un nouveau partage.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Journey share {self.source_journey_id or 'source indisponible'}"


class JourneyShareAcceptance(models.Model):
    """Functional provenance and idempotence boundary for Journey materialization."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.OneToOneField(
        ShareDelivery,
        on_delete=models.PROTECT,
        related_name="journey_acceptance",
    )
    resulting_journey = models.OneToOneField(
        "journeys.Journey",
        on_delete=models.PROTECT,
        related_name="share_origin",
    )
    accepted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-accepted_at", "id"]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = JourneyShareAcceptance.objects.filter(pk=self.pk).values(
                "delivery_id", "resulting_journey_id", "accepted_at"
            ).first()
            current = {
                "delivery_id": self.delivery_id,
                "resulting_journey_id": self.resulting_journey_id,
                "accepted_at": self.accepted_at,
            }
            if previous and previous != current:
                raise ValidationError("Une acceptation Journey est un lien d’audit immuable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Une acceptation Journey auditée ne peut pas être supprimée.")

    def __str__(self):
        return f"{self.delivery_id} → {self.resulting_journey_id}"
