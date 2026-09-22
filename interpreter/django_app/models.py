from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from interpreter.contracts import CandidateKind, InterpretationLifecycle, InterpretationOutcome

LIFECYCLE_CHOICES = [(item.value, item.value) for item in InterpretationLifecycle]
OUTCOME_CHOICES = [(item.value, item.value) for item in InterpretationOutcome]
CANDIDATE_KIND_CHOICES = [(item.value, item.value) for item in CandidateKind]


class InterpretationRun(models.Model):
    interpretation_ref = models.CharField(max_length=255, unique=True)
    observation_ref = models.CharField(max_length=255, db_index=True)
    material_key = models.CharField(max_length=255)
    target_key = models.CharField(max_length=96, db_index=True)
    strategy_key = models.CharField(max_length=120)
    strategy_version = models.CharField(max_length=80)
    strategy_fingerprint = models.CharField(max_length=128)
    lifecycle = models.CharField(max_length=16, choices=LIFECYCLE_CHOICES, default=InterpretationLifecycle.PENDING.value)
    outcome = models.CharField(max_length=32, choices=OUTCOME_CHOICES, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=120, blank=True)
    warning_codes = models.JSONField(default=list, blank=True)
    stats = models.JSONField(default=dict, blank=True)
    claim_token = models.UUIDField(null=True, blank=True, db_index=True)
    claimed_by = models.CharField(max_length=120, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    prospector_reported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "interpreter_run"
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["material_key", "strategy_fingerprint"], name="int_run_material_strategy_uq"),
            models.CheckConstraint(
                condition=(
                    Q(lifecycle="pending", claim_token__isnull=True, claimed_by="", lease_expires_at__isnull=True, outcome="", started_at__isnull=True, completed_at__isnull=True)
                    | (Q(lifecycle="processing", claim_token__isnull=False, lease_expires_at__isnull=False, started_at__isnull=False, completed_at__isnull=True, outcome="") & ~Q(claimed_by=""))
                    | (Q(lifecycle="finalized", claim_token__isnull=True, claimed_by="", lease_expires_at__isnull=True, started_at__isnull=False, completed_at__isnull=False) & ~Q(outcome=""))
                ),
                name="int_run_lifecycle_consistent",
            ),
            models.CheckConstraint(
                condition=(Q(outcome="failed") & ~Q(failure_code="")) | (~Q(outcome="failed") & Q(failure_code="")),
                name="int_run_failure_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["lifecycle", "lease_expires_at", "id"], name="int_run_lease_idx"),
            models.Index(fields=["observation_ref", "strategy_fingerprint"], name="int_run_observation_idx"),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.warning_codes, list):
            raise ValidationError({"warning_codes": "warning_codes must be a list"})
        if not isinstance(self.stats, dict):
            raise ValidationError({"stats": "stats must be an object"})

    def __str__(self):
        return self.interpretation_ref


class InterpretationCandidate(models.Model):
    run = models.ForeignKey(InterpretationRun, on_delete=models.CASCADE, related_name="candidate_rows")
    candidate_ref = models.CharField(max_length=255, unique=True)
    ordinal = models.PositiveIntegerField()
    kind = models.CharField(max_length=24, choices=CANDIDATE_KIND_CHOICES)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "interpreter_candidate"
        ordering = ["run", "ordinal"]
        constraints = [
            models.UniqueConstraint(fields=["run", "ordinal"], name="int_candidate_ordinal_uq"),
            models.CheckConstraint(condition=Q(ordinal__gte=1), name="int_candidate_ordinal_gte_1"),
        ]
        indexes = [models.Index(fields=["run", "kind", "ordinal"], name="int_candidate_kind_idx")]

    def __str__(self):
        return self.candidate_ref


class InterpretationArtifactUse(models.Model):
    run = models.ForeignKey(InterpretationRun, on_delete=models.CASCADE, related_name="artifact_use_rows")
    ordinal = models.PositiveIntegerField()
    artifact_ref = models.CharField(max_length=255)
    artifact_observation_ref = models.CharField(max_length=255)
    role = models.CharField(max_length=64)
    media_type = models.CharField(max_length=180, blank=True)
    content_digest = models.CharField(max_length=64)
    selection_reason = models.CharField(max_length=120)
    completeness = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "interpreter_artifact_use"
        ordering = ["run", "ordinal"]
        constraints = [
            models.UniqueConstraint(fields=["run", "ordinal"], name="int_artifact_use_ordinal_uq"),
            models.UniqueConstraint(fields=["run", "artifact_ref"], name="int_artifact_use_ref_uq"),
            models.CheckConstraint(condition=Q(ordinal__gte=1), name="int_artifact_use_ordinal_gte_1"),
        ]
        indexes = [models.Index(fields=["artifact_ref", "id"], name="int_artifact_ref_idx")]

    def __str__(self):
        return f"{self.run_id}:{self.artifact_ref}"
