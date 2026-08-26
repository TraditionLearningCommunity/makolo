import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class AccessStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    VALID = "valid", "Valide"
    USED = "used", "Utilisé"
    CANCELLED = "cancelled", "Annulé"
    REVOKED = "revoked", "Révoqué"
    EXPIRED = "expired", "Expiré"
    TRANSFERRED = "transferred", "Transféré"


TERMINAL_ACCESS_STATUSES = {
    AccessStatus.USED,
    AccessStatus.CANCELLED,
    AccessStatus.REVOKED,
    AccessStatus.EXPIRED,
    AccessStatus.TRANSFERRED,
}


class Access(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="access_rights",
        null=True,
        blank=True,
    )
    external_beneficiary = models.ForeignKey(
        "journeys.ExternalBeneficiary",
        on_delete=models.PROTECT,
        related_name="access_rights",
        null=True,
        blank=True,
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.PROTECT,
        related_name="access_rights",
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.PROTECT,
        related_name="access_rights",
        null=True,
        blank=True,
    )
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.SET_NULL,
        related_name="accesses",
        null=True,
        blank=True,
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="issued_access_rights",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=16, choices=AccessStatus.choices, default=AccessStatus.PENDING)
    single_use = models.BooleanField(default=True)
    source_key = models.CharField(
        max_length=180,
        blank=True,
        help_text="Clé d’idempotence métier dans la Démarche (ex. ticket:<uuid>).",
    )
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["beneficiary", "status"], name="access_beneficiary_status_idx"),
            models.Index(fields=["external_beneficiary", "status"], name="access_extben_status_idx"),
            models.Index(fields=["activity", "status"], name="access_activity_status_idx"),
            models.Index(fields=["occurrence", "status"], name="access_occurrence_status_idx"),
            models.Index(fields=["valid_until"], name="access_valid_until_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_from__isnull=True) | Q(valid_until__isnull=True) | Q(valid_until__gt=models.F("valid_from")),
                name="access_valid_window",
            ),
            models.CheckConstraint(
                condition=(Q(beneficiary__isnull=False) & Q(external_beneficiary__isnull=True))
                | (Q(beneficiary__isnull=True) & Q(external_beneficiary__isnull=False)),
                name="access_exactly_one_beneficiary",
            ),
            models.UniqueConstraint(
                fields=["journey", "source_key"],
                condition=Q(journey__isnull=False) & ~Q(source_key=""),
                name="access_journey_source_unique",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            errors["valid_until"] = "La fin de validité doit être postérieure au début."
        if self.occurrence_id and self.activity_id and self.occurrence.activity_id != self.activity_id:
            errors["occurrence"] = "L’Occurrence doit appartenir à la même Activity que l’Accès."
        if self.journey_id and self.activity_id and self.journey.activity_id != self.activity_id:
            errors["journey"] = "La Démarche doit concerner la même Activity que l’Accès."
        if self.journey_id and self.occurrence_id and self.journey.occurrence_id:
            if self.journey.occurrence_id != self.occurrence_id:
                errors["occurrence"] = "L’Occurrence de l’Accès doit être cohérente avec celle de la Démarche."
        if bool(self.beneficiary_id) == bool(self.external_beneficiary_id):
            errors["beneficiary"] = "L’Accès doit avoir exactement un bénéficiaire, Profile ou externe."
        if self.journey_id:
            if self.journey.beneficiary_id and self.beneficiary_id != self.journey.beneficiary_id:
                errors["beneficiary"] = "Le bénéficiaire Profile doit correspondre à celui de la Démarche."
            if self.journey.external_beneficiary_id and self.external_beneficiary_id != self.journey.external_beneficiary_id:
                errors["external_beneficiary"] = "Le bénéficiaire externe doit correspondre à celui de la Démarche."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = Access.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez les services Access pour changer cet état."})
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

    def __str__(self):
        return f"{self.beneficiary_display_name} — {self.activity} — {self.get_status_display()}"


class CredentialType(models.TextChoices):
    QR = "qr", "QR"
    BARCODE = "barcode", "Code-barres"
    PASS = "pass", "Pass"
    DIGITAL_BADGE = "digital_badge", "Badge numérique"


class CredentialStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    REVOKED = "revoked", "Révoqué"
    EXPIRED = "expired", "Expiré"


class AccessCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access = models.ForeignKey(Access, on_delete=models.CASCADE, related_name="credentials")
    credential_type = models.CharField(max_length=24, choices=CredentialType.choices, default=CredentialType.QR)
    status = models.CharField(max_length=16, choices=CredentialStatus.choices, default=CredentialStatus.ACTIVE)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    version = models.PositiveIntegerField(default=1)
    issued_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["access", "-version", "-issued_at"]
        constraints = [
            models.UniqueConstraint(fields=["access", "version"], name="access_credential_version_unique"),
        ]
        indexes = [
            models.Index(fields=["access", "status"], name="access_credential_status_idx"),
            models.Index(fields=["public_id", "version"], name="access_credential_lookup_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = AccessCredential.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez les services de rotation/révocation du credential."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def __str__(self):
        return f"{self.get_credential_type_display()} v{self.version} — {self.get_status_display()}"


class AccessUseResult(models.TextChoices):
    ACCEPTED = "accepted", "Accepté"
    ALREADY_USED = "already_used", "Déjà utilisé"
    EXPIRED = "expired", "Expiré"
    NOT_YET_VALID = "not_yet_valid", "Pas encore valide"
    REVOKED = "revoked", "Révoqué"
    CANCELLED = "cancelled", "Annulé"
    WRONG_ACTIVITY = "wrong_activity", "Mauvaise Activity"
    WRONG_OCCURRENCE = "wrong_occurrence", "Mauvaise Occurrence"
    INVALID_CREDENTIAL = "invalid_credential", "Credential invalide"


class AccessUse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access = models.ForeignKey(Access, on_delete=models.PROTECT, related_name="uses")
    credential = models.ForeignKey(
        AccessCredential,
        on_delete=models.SET_NULL,
        related_name="uses",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="access_uses_controlled",
        null=True,
        blank=True,
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.SET_NULL,
        related_name="access_uses",
        null=True,
        blank=True,
    )
    result = models.CharField(max_length=32, choices=AccessUseResult.choices)
    source = models.CharField(max_length=80, blank=True)
    client_reference = models.CharField(
        max_length=64,
        blank=True,
        help_text="Référence idempotente du cycle de contrôle. Aucun credential brut n’est stocké ici.",
    )
    used_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-used_at", "id"]
        indexes = [
            models.Index(fields=["access", "used_at"], name="access_use_access_time_idx"),
            models.Index(fields=["occurrence", "used_at"], name="access_use_occurrence_time_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "client_reference"],
                condition=Q(actor__isnull=False) & ~Q(client_reference=""),
                name="access_use_actor_client_ref_unique",
            ),
        ]

    def __str__(self):
        return f"{self.access_id} — {self.get_result_display()}"
