import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

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


class RequirementReuseApplication(models.Model):
    """Privacy-safe append-only audit for one explicit Trusted Reuse application."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(
        "services.ServiceRequirementAssessment",
        on_delete=models.PROTECT,
        related_name="trusted_reuse_applications",
    )
    policy = models.ForeignKey(
        RequirementReusePolicy,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    source_type = models.CharField(max_length=24, choices=RequirementReuseSource.choices)
    source_asset_version = models.ForeignKey(
        "personal_assets.PersonalAssetVersion",
        on_delete=models.PROTECT,
        related_name="requirement_reuse_applications",
        null=True,
        blank=True,
    )
    source_journey_artifact = models.ForeignKey(
        "journeys.JourneyArtifact",
        on_delete=models.PROTECT,
        related_name="source_requirement_reuse_applications",
        null=True,
        blank=True,
    )
    source_proof = models.ForeignKey(
        "trust.Proof",
        on_delete=models.PROTECT,
        related_name="requirement_reuse_applications",
        null=True,
        blank=True,
    )
    intermediate_asset_version = models.ForeignKey(
        "personal_assets.PersonalAssetVersion",
        on_delete=models.PROTECT,
        related_name="intermediate_requirement_reuse_applications",
        null=True,
        blank=True,
    )
    decision = models.CharField(max_length=40)
    reason_codes = models.JSONField(default=list)
    freshness = models.CharField(max_length=32, blank=True)
    sensitivity = models.CharField(max_length=16, blank=True)
    source_status = models.CharField(max_length=32, blank=True)
    source_version = models.PositiveIntegerField(null=True, blank=True)
    confirmation_confirmed = models.BooleanField(default=False)
    materialization_path = models.CharField(max_length=80, blank=True)
    materialized_artifact = models.ForeignKey(
        "journeys.JourneyArtifact",
        on_delete=models.PROTECT,
        related_name="trusted_reuse_materializations",
        null=True,
        blank=True,
    )
    evidence = models.ForeignKey(
        "services.ServiceRequirementEvidence",
        on_delete=models.PROTECT,
        related_name="trusted_reuse_applications",
        null=True,
        blank=True,
    )
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requirement_reuse_applications",
    )
    observed_at = models.DateTimeField()
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-applied_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(source_asset_version__isnull=False, source_journey_artifact__isnull=True, source_proof__isnull=True)
                    | Q(source_asset_version__isnull=True, source_journey_artifact__isnull=False, source_proof__isnull=True)
                    | Q(source_asset_version__isnull=True, source_journey_artifact__isnull=True, source_proof__isnull=False)
                ),
                name="req_reuse_app_one_source",
            ),
            models.UniqueConstraint(
                fields=["assessment", "source_asset_version"],
                condition=Q(source_asset_version__isnull=False),
                name="req_reuse_app_asset_unique",
            ),
            models.UniqueConstraint(
                fields=["assessment", "source_journey_artifact"],
                condition=Q(source_journey_artifact__isnull=False),
                name="req_reuse_app_art_unique",
            ),
            models.UniqueConstraint(
                fields=["assessment", "source_proof"],
                condition=Q(source_proof__isnull=False),
                name="req_reuse_app_proof_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["assessment", "applied_at"], name="req_reuse_app_assess_idx"),
            models.Index(fields=["policy", "applied_at"], name="req_reuse_app_policy_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        source_ids = [self.source_asset_version_id, self.source_journey_artifact_id, self.source_proof_id]
        if sum(bool(value) for value in source_ids) != 1:
            errors["source_type"] = "Une application Trusted Reuse doit référencer exactement une source canonique."
        expected = {
            RequirementReuseSource.LIBRARY: self.source_asset_version_id,
            RequirementReuseSource.JOURNEY_ARTIFACT: self.source_journey_artifact_id,
            RequirementReuseSource.PROOF: self.source_proof_id,
        }.get(self.source_type)
        if not expected:
            errors["source_type"] = "Le type de source ne correspond pas à la relation canonique renseignée."
        if self.assessment_id and self.policy_id and self.assessment.requirement_id != self.policy.requirement_id:
            errors["policy"] = "La policy doit appartenir au Requirement de l’Assessment."
        if self.materialized_artifact_id and self.assessment_id:
            if self.materialized_artifact.journey_id != self.assessment.context.journey_id:
                errors["materialized_artifact"] = "L’Artifact matérialisé doit appartenir à la Journey cible."
        if self.evidence_id:
            if self.evidence.assessment_id != self.assessment_id:
                errors["evidence"] = "L’Evidence doit appartenir au même Assessment."
            if self.materialized_artifact_id and self.evidence.artifact_id != self.materialized_artifact_id:
                errors["evidence"] = "L’Evidence doit référencer l’Artifact matérialisé exact."
        if self.source_type == RequirementReuseSource.PROOF and (self.materialized_artifact_id or self.evidence_id):
            errors["source_type"] = "Une Proof Trust ne doit pas être transformée en faux JourneyArtifact."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Un audit Trusted Reuse est append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un audit Trusted Reuse ne peut pas être supprimé silencieusement.")
