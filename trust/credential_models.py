import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


CREDENTIAL_HISTORY_DELETE_ERROR = (
    "Un Credential délivré appartient à l’historique Trust et ne peut pas être supprimé."
)
CREDENTIAL_BULK_UPDATE_ERROR = (
    "Un Credential délivré ne peut pas être modifié en masse ; utilisez les services Trust contrôlés."
)


class CredentialType(models.TextChoices):
    PARTICIPATION = "participation", "Attestation de participation"
    COMPLETION = "completion", "Certificat de complétion"
    ATTESTATION = "attestation", "Autre attestation"


class CredentialStatus(models.TextChoices):
    ISSUED = "issued", "Valide"
    REVOKED = "revoked", "Révoquée"


class CredentialQuerySet(models.QuerySet):
    def delete(self):
        # Refuse before Django's deletion Collector enters its atomic block.
        # This protects bulk/admin deletion without poisoning caller transactions.
        raise ValidationError(CREDENTIAL_HISTORY_DELETE_ERROR)

    def update(self, **kwargs):
        raise ValidationError(CREDENTIAL_BULK_UPDATE_ERROR)

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError(CREDENTIAL_BULK_UPDATE_ERROR)


class Credential(models.Model):
    """Issuer-backed attestation over canonical Makolo business sources.

    Credential is deliberately distinct from Proof (a Makolo-established fact)
    and JourneyArtifact (a versioned Journey document). Its issuer is captured
    at issuance from the source Activity's canonical logical operator.
    """

    objects = CredentialQuerySet.as_manager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    subject_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="trust_credentials",
    )
    issuer_space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="issued_trust_credentials",
        null=True,
        blank=True,
    )
    issuer_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issued_trust_credentials_as_profile",
        null=True,
        blank=True,
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issued_trust_credentials_audit",
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.PROTECT,
        related_name="trust_credentials",
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.PROTECT,
        related_name="trust_credentials",
        null=True,
        blank=True,
    )
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.PROTECT,
        related_name="trust_credentials",
        null=True,
        blank=True,
    )
    credential_type = models.CharField(max_length=24, choices=CredentialType.choices)
    title = models.CharField(max_length=220)
    statement = models.TextField(blank=True, max_length=3000)
    status = models.CharField(max_length=12, choices=CredentialStatus.choices, default=CredentialStatus.ISSUED)
    issued_at = models.DateTimeField(default=timezone.now)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="revoked_trust_credentials",
        null=True,
        blank=True,
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "trust"
        ordering = ["-issued_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(issuer_space__isnull=False, issuer_profile__isnull=True)
                    | Q(issuer_space__isnull=True, issuer_profile__isnull=False)
                ),
                name="trust_cred_exactly_one_issuer",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=CredentialStatus.ISSUED, revoked_at__isnull=True, revoked_by__isnull=True)
                    | Q(status=CredentialStatus.REVOKED, revoked_at__isnull=False, revoked_by__isnull=False)
                ),
                name="trust_cred_revocation_state",
            ),
        ]
        indexes = [
            models.Index(fields=["subject_profile", "status"], name="trust_cred_subject_idx"),
            models.Index(fields=["issuer_space", "status"], name="trust_cred_space_idx"),
            models.Index(fields=["issuer_profile", "status"], name="trust_cred_profile_idx"),
            models.Index(fields=["public_id", "status"], name="trust_cred_public_idx"),
        ]

    @property
    def issuer_display_name(self):
        if self.issuer_space_id:
            return self.issuer_space.name
        if self.issuer_profile_id:
            full_name = self.issuer_profile.get_full_name().strip()
            return full_name or self.issuer_profile.username
        return ""

    @property
    def subject_display_name(self):
        full_name = self.subject_profile.get_full_name().strip()
        return full_name or self.subject_profile.username

    @property
    def verification_state(self):
        return "revoked" if self.status == CredentialStatus.REVOKED else "valid"

    def clean(self):
        super().clean()
        errors = {}
        if bool(self.issuer_space_id) == bool(self.issuer_profile_id):
            errors["issuer_space"] = "Un Credential doit avoir exactement un émetteur, Espace ou Profile."
        if not (self.title or "").strip():
            errors["title"] = "Le titre du Credential est obligatoire."

        # Validate the issuer against the current canonical owner only when the
        # attestation is first issued. Later ownership changes must not rewrite
        # historical issuer truth or prevent a controlled revocation.
        if self._state.adding and self.activity_id:
            if self.activity.space_id:
                if self.issuer_space_id != self.activity.space_id or self.issuer_profile_id:
                    errors["issuer_space"] = "L’émetteur doit être l’Espace opérateur canonique de l’Activity."
            elif self.activity.owner_profile_id:
                if self.issuer_profile_id != self.activity.owner_profile_id or self.issuer_space_id:
                    errors["issuer_profile"] = "L’émetteur doit être le Profile opérateur canonique de l’Activity."
            else:
                errors["activity"] = "Cette Activity historique ne possède pas d’opérateur logique permettant une émission sûre."

        if self.occurrence_id and self.activity_id and self.occurrence.activity_id != self.activity_id:
            errors["occurrence"] = "L’Occurrence doit appartenir à l’Activity source du Credential."
        if self.journey_id and self.activity_id and self.journey.activity_id != self.activity_id:
            errors["journey"] = "La Journey doit concerner l’Activity source du Credential."
        if self.journey_id:
            if self.journey.beneficiary_id != self.subject_profile_id:
                errors["subject_profile"] = "Le bénéficiaire du Credential doit être le bénéficiaire Profile de la Journey."
            if self.occurrence_id and self.journey.occurrence_id and self.journey.occurrence_id != self.occurrence_id:
                errors["occurrence"] = "L’Occurrence du Credential doit correspondre à celle de la Journey."

        if self.status == CredentialStatus.REVOKED:
            if not self.revoked_at:
                errors["revoked_at"] = "Un Credential révoqué doit conserver sa date de révocation."
            if not self.revoked_by_id:
                errors["revoked_by"] = "Un Credential révoqué doit conserver l’acteur de la révocation."
        if self.status == CredentialStatus.ISSUED and any([self.revoked_by_id, self.revoked_at, self.revoke_reason]):
            errors["status"] = "Un Credential valide ne peut pas porter de métadonnées de révocation."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.title = (self.title or "").strip()
        self.statement = (self.statement or "").strip()
        self.revoke_reason = (self.revoke_reason or "").strip()
        self.full_clean()
        if self.pk and not self._state.adding:
            previous = Credential.objects.filter(pk=self.pk).values(
                "public_id",
                "subject_profile_id",
                "issuer_space_id",
                "issuer_profile_id",
                "issued_by_id",
                "activity_id",
                "occurrence_id",
                "journey_id",
                "credential_type",
                "title",
                "statement",
                "issued_at",
                "status",
                "revoked_by_id",
                "revoked_at",
                "revoke_reason",
            ).first()
            immutable = {
                "public_id": self.public_id,
                "subject_profile_id": self.subject_profile_id,
                "issuer_space_id": self.issuer_space_id,
                "issuer_profile_id": self.issuer_profile_id,
                "issued_by_id": self.issued_by_id,
                "activity_id": self.activity_id,
                "occurrence_id": self.occurrence_id,
                "journey_id": self.journey_id,
                "credential_type": self.credential_type,
                "title": self.title,
                "statement": self.statement,
                "issued_at": self.issued_at,
            }
            if previous is not None and any(previous[name] != value for name, value in immutable.items()):
                raise ValidationError("Un Credential délivré est immuable ; révoquez-le puis délivrez-en un nouveau.")
            if previous is not None and previous["status"] != self.status and not getattr(self, "_allow_status_transition", False):
                raise ValidationError({"status": "Utilisez le service Trust de révocation du Credential."})
            if previous is not None and previous["status"] == CredentialStatus.REVOKED:
                revoked_fields = ("revoked_by_id", "revoked_at", "revoke_reason")
                if any(previous[name] != getattr(self, name) for name in revoked_fields):
                    raise ValidationError("Les métadonnées de révocation d’un Credential sont immuables.")
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def delete(self, *args, **kwargs):
        raise ValidationError(CREDENTIAL_HISTORY_DELETE_ERROR)
