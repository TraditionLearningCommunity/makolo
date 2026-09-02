from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from journeys.collaboration_models import JourneyArtifactKind
from trust.models import ProofType


class OpportunityRequirementReusePolicy(models.Model):
    """Explicit, version-bound acceptance policy for Trusted Reuse.

    The policy belongs to the canonical OpportunityRequirement. It is deliberately
    small: supported source classes, one exact artifact kind and/or one exact Proof
    type, plus an optional contextual maximum age. Published Opportunity revisions
    make their policy immutable together with the Requirement they describe.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requirement = models.OneToOneField(
        "opportunities.OpportunityRequirement",
        on_delete=models.CASCADE,
        related_name="trusted_reuse_policy",
    )
    allow_library = models.BooleanField(default=False)
    allow_journey_artifact = models.BooleanField(default=False)
    allow_proof = models.BooleanField(default=False)
    accepted_artifact_kind = models.CharField(
        max_length=32,
        choices=JourneyArtifactKind.choices,
        blank=True,
    )
    accepted_proof_type = models.CharField(
        max_length=32,
        choices=ProofType.choices,
        blank=True,
    )
    max_age_days = models.PositiveIntegerField(null=True, blank=True)
    allow_unknown_freshness = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(max_age_days__isnull=True) | Q(max_age_days__gte=1),
                name="opp_reuse_policy_age_positive",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        allows_document = self.allow_library or self.allow_journey_artifact
        if not any((allows_document, self.allow_proof)):
            errors["allow_library"] = "La policy doit autoriser au moins une source Trusted Reuse."
        if allows_document and not self.accepted_artifact_kind:
            errors["accepted_artifact_kind"] = "Une source documentaire exige un JourneyArtifactKind explicite."
        if not allows_document and self.accepted_artifact_kind:
            errors["accepted_artifact_kind"] = "Un JourneyArtifactKind exige une source documentaire autorisée."
        if self.allow_proof and not self.accepted_proof_type:
            errors["accepted_proof_type"] = "Une source Proof exige un ProofType explicite."
        if not self.allow_proof and self.accepted_proof_type:
            errors["accepted_proof_type"] = "Un ProofType exige que la source Proof soit autorisée."
        if self.max_age_days is not None and self.max_age_days < 1:
            errors["max_age_days"] = "La fenêtre de fraîcheur doit être d’au moins un jour."
        if self.requirement_id and self.requirement.revision.published_at is not None:
            persisted = type(self).objects.filter(pk=self.pk).exists() if self.pk else False
            if self._state.adding or persisted:
                errors["requirement"] = "La policy d’un Requirement publié est immuable."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.requirement.revision.published_at is not None:
            raise ValidationError("La policy d’un Requirement publié ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)
