import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ExternalBeneficiary(models.Model):
    """Minimal identity for a holder who does not have a Makolo account.

    This is deliberately not a CRM contact and never authenticates. It exists
    only so a Journey/Access can name the individual who receives the right
    without manufacturing a User row.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=180)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_external_beneficiaries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name", "id"]
        indexes = [
            models.Index(fields=["created_by", "created_at"], name="journey_extben_creator_idx"),
            models.Index(fields=["email"], name="journey_extben_email_idx"),
        ]

    def clean(self):
        super().clean()
        self.display_name = (self.display_name or "").strip()
        self.email = (self.email or "").strip().lower()
        self.phone = (self.phone or "").strip()
        if not self.display_name:
            raise ValidationError({"display_name": "Le nom du bénéficiaire est obligatoire."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class WorkflowKind(models.TextChoices):
    PURCHASE = "purchase", "Achat"
    ORDER_APPROVAL = "order_approval", "Commande avec approbation"
    RESERVATION = "reservation", "Réservation"
    REGISTRATION = "registration", "Inscription"
    INVITATION = "invitation", "Invitation"


class JourneyStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    SUBMITTED = "submitted", "Soumise"
    PENDING_APPROVAL = "pending_approval", "En attente d’approbation"
    APPROVED = "approved", "Approuvée"
    PENDING_PAYMENT = "pending_payment", "En attente de paiement"
    CONFIRMED = "confirmed", "Confirmée"
    FULFILLED = "fulfilled", "Réalisée"
    REJECTED = "rejected", "Rejetée"
    CANCELLED = "cancelled", "Annulée"
    EXPIRED = "expired", "Expirée"


TERMINAL_JOURNEY_STATUSES = {
    JourneyStatus.FULFILLED,
    JourneyStatus.REJECTED,
    JourneyStatus.CANCELLED,
    JourneyStatus.EXPIRED,
}


class Journey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="initiated_journeys",
    )
    beneficiary = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="beneficiary_journeys",
        null=True,
        blank=True,
    )
    external_beneficiary = models.ForeignKey(
        ExternalBeneficiary,
        on_delete=models.PROTECT,
        related_name="journeys",
        null=True,
        blank=True,
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.PROTECT,
        related_name="journeys",
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.PROTECT,
        related_name="journeys",
        null=True,
        blank=True,
    )
    workflow = models.CharField(max_length=32, choices=WorkflowKind.choices)
    status = models.CharField(
        max_length=32,
        choices=JourneyStatus.choices,
        default=JourneyStatus.DRAFT,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["beneficiary", "status"], name="journey_beneficiary_status_idx"),
            models.Index(fields=["external_beneficiary", "status"], name="journey_extben_status_idx"),
            models.Index(fields=["activity", "status"], name="journey_activity_status_idx"),
            models.Index(fields=["occurrence", "status"], name="journey_occurrence_status_idx"),
            models.Index(fields=["workflow", "status"], name="journey_workflow_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(Q(beneficiary__isnull=False) & Q(external_beneficiary__isnull=True))
                | (Q(beneficiary__isnull=True) & Q(external_beneficiary__isnull=False)),
                name="journey_exactly_one_beneficiary",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.occurrence_id and self.activity_id:
            occurrence_activity_id = self.occurrence.activity_id
            if occurrence_activity_id != self.activity_id:
                errors["occurrence"] = "L’Occurrence doit appartenir à la même Activity que la Démarche."
        if bool(self.beneficiary_id) == bool(self.external_beneficiary_id):
            errors["beneficiary"] = "La Démarche doit avoir exactement un bénéficiaire, Profile ou externe."
        if self._state.adding and self.activity_id and not errors.get("beneficiary"):
            from groups.community_services import profile_is_eligible_for_activity

            eligible_profile = self.beneficiary if self.beneficiary_id else None
            if not profile_is_eligible_for_activity(eligible_profile, self.activity):
                errors["beneficiary"] = (
                    "Cette Activity est réservée aux membres actifs d'un Groupe autorisé."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = Journey.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError(
                    {"status": "Utilisez le service de transition des Démarches pour changer cet état."}
                )
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    @property
    def beneficiary_display_name(self):
        if self.beneficiary_id:
            full_name = self.beneficiary.get_full_name().strip()
            return full_name or self.beneficiary.username
        return self.external_beneficiary.display_name if self.external_beneficiary_id else ""

    @property
    def is_external_beneficiary(self):
        return bool(self.external_beneficiary_id)

    @property
    def is_terminal(self):
        return self.status in TERMINAL_JOURNEY_STATUSES

    def __str__(self):
        return f"{self.get_workflow_display()} — {self.beneficiary_display_name} — {self.get_status_display()}"


class JourneyTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(Journey, on_delete=models.CASCADE, related_name="transitions")
    from_status = models.CharField(max_length=32, choices=JourneyStatus.choices)
    to_status = models.CharField(max_length=32, choices=JourneyStatus.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="journey_transitions",
        null=True,
        blank=True,
    )
    reason = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["journey", "created_at"], name="journey_transition_time_idx")]

    def __str__(self):
        return f"{self.journey_id}: {self.from_status} → {self.to_status}"


class RequestPurpose(models.TextChoices):
    APPROVAL = "approval", "Validation"
    REGISTRATION = "registration", "Inscription"
    RESERVATION = "reservation", "Réservation"
    INVITATION = "invitation", "Invitation"
    PARTICIPATION = "participation", "Participation"
    OTHER = "other", "Autre"


class RequestStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    APPROVED = "approved", "Approuvée"
    REJECTED = "rejected", "Rejetée"
    CANCELLED = "cancelled", "Annulée"
    EXPIRED = "expired", "Expirée"


class JourneyRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(Journey, on_delete=models.CASCADE, related_name="requests")
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="journey_requests_made",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="journey_requests_decided",
        null=True,
        blank=True,
    )
    purpose = models.CharField(
        max_length=32,
        choices=RequestPurpose.choices,
        default=RequestPurpose.APPROVAL,
    )
    status = models.CharField(
        max_length=16,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
    )
    message = models.TextField(blank=True)
    decision_comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["journey", "status"], name="journey_request_status_idx"),
            models.Index(fields=["status", "created_at"], name="journey_request_queue_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(expires_at__isnull=True) | Q(expires_at__gt=models.F("submitted_at")),
                name="journey_request_expiry_after_submit",
            )
        ]

    def clean(self):
        super().clean()
        if self.expires_at and self.submitted_at and self.expires_at <= self.submitted_at:
            raise ValidationError({"expires_at": "L’expiration doit être postérieure à la soumission."})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = JourneyRequest.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError(
                    {"status": "Utilisez le service de décision des Demandes pour changer cet état."}
                )
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    @property
    def is_pending(self):
        return self.status == RequestStatus.PENDING

    def __str__(self):
        return f"{self.get_purpose_display()} — {self.journey_id} — {self.get_status_display()}"
