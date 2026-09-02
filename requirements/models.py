import uuid

from django.core.exceptions import ValidationError
from django.db import models

from journeys.collaboration_models import JourneyArtifactKind
from trust.models import ProofType


class RequirementReuseSource(models.TextChoices):
    LIBRARY = "library", "Ma Bibliothèque"
    JOURNEY_ARTIFACT = "journey_artifact", "JourneyArtifact historique"
    PROOF = "proof", "Proof Trust"


class RequirementReusePolicy(models.Model):
    """Explicit contextual acceptance policy owned by a versioned Requirement.

    A policy never makes a Requirement universally satisfied. It only declares
    which exact source/type can be considered by Trusted Reuse for this one
    OpportunityRequirement. The linked OpportunityRevision provides policy
    versioning: once published, both Requirement and policy are immutable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requirement = models.ForeignKey(
        "opportunities.OpportunityRequirement",
        on_delete=models.CASCADE,
        related_name="reuse_policies",
    )
    key = models.SlugField(max_length=80)
    source_type = models.CharField(max_length=24, choices=RequirementReuseSource.choices)
    artifact_kind = models.CharField(max_length=32, choices=JourneyArtifactKind.choices, blank=True)
    proof_type = models.CharField(max_length=32, choices=ProofType.choices, blank=True)
    require_not_expired = models.BooleanField(default=True)
    max_age_days = models.PositiveIntegerField(null=True, blank=True)
    allow_sensitive_with_confirmation = models.BooleanField(default=False)
    allow_restricted_with_confirmation = models.BooleanField(default=False)
    human_review_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["requirement", "key", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["requirement", "key"], name="req_reuse_policy_key_unique"),
        ]
        indexes = [
            models.Index(fields=["requirement", "source_type"], name="req_reuse_policy_src_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        is_proof = self.source_type == RequirementReuseSource.PROOF
        if is_proof:
            if not self.proof_type:
                errors["proof_type"] = "Une policy Proof doit déclarer un ProofType exact."
            if self.artifact_kind:
                errors["artifact_kind"] = "Une policy Proof ne porte pas de JourneyArtifactKind."
        else:
            if not self.artifact_kind:
                errors["artifact_kind"] = "Une policy documentaire doit déclarer un JourneyArtifactKind exact."
            if self.proof_type:
                errors["proof_type"] = "Une policy documentaire ne porte pas de ProofType."
        if self.max_age_days is not None and self.max_age_days < 1:
            errors["max_age_days"] = "La fenêtre de fraîcheur doit être d’au moins un jour."
        if self.requirement_id and self.requirement.revision.published_at is not None:
            errors["requirement"] = "La policy d’un Requirement publié est immuable."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Une policy Trusted Reuse est immuable ; versionnez le Requirement.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.requirement.revision.published_at is not None:
            raise ValidationError("La policy d’un Requirement publié ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)
