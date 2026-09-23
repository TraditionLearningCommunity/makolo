from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from resolver.contracts import (
    AssertionKind,
    ResolutionLifecycle,
    ResolutionOutcome,
    ResolutionStatus,
)

LIFECYCLE_CHOICES = [(item.value, item.value) for item in ResolutionLifecycle]
OUTCOME_CHOICES = [(item.value, item.value) for item in ResolutionOutcome]
ASSERTION_KIND_CHOICES = [(item.value, item.value) for item in AssertionKind]
STATUS_CHOICES = [(item.value, item.value) for item in ResolutionStatus]


class ResolutionRun(models.Model):
    resolution_ref = models.CharField(max_length=255, unique=True)
    interpretation_ref = models.CharField(max_length=255, db_index=True)
    material_key = models.CharField(max_length=255)
    observation_ref = models.CharField(max_length=255, db_index=True)
    target_key = models.CharField(max_length=96, db_index=True)
    strategy_key = models.CharField(max_length=120)
    strategy_version = models.CharField(max_length=80)
    strategy_fingerprint = models.CharField(max_length=128)
    lifecycle = models.CharField(
        max_length=16,
        choices=LIFECYCLE_CHOICES,
        default=ResolutionLifecycle.PENDING.value,
    )
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
        db_table = "resolver_run"
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["interpretation_ref", "strategy_fingerprint"],
                name="res_run_interp_strategy_uq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        lifecycle="pending",
                        claim_token__isnull=True,
                        claimed_by="",
                        lease_expires_at__isnull=True,
                        outcome="",
                        started_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | (
                        Q(
                            lifecycle="processing",
                            claim_token__isnull=False,
                            lease_expires_at__isnull=False,
                            started_at__isnull=False,
                            completed_at__isnull=True,
                            outcome="",
                        )
                        & ~Q(claimed_by="")
                    )
                    | (
                        Q(
                            lifecycle="finalized",
                            claim_token__isnull=True,
                            claimed_by="",
                            lease_expires_at__isnull=True,
                            started_at__isnull=False,
                            completed_at__isnull=False,
                        )
                        & ~Q(outcome="")
                    )
                ),
                name="res_run_lifecycle_consistent",
            ),
            models.CheckConstraint(
                condition=(Q(outcome="failed") & ~Q(failure_code=""))
                | (~Q(outcome="failed") & Q(failure_code="")),
                name="res_run_failure_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["lifecycle", "lease_expires_at", "id"], name="res_run_lease_idx"),
            models.Index(fields=["interpretation_ref", "strategy_fingerprint"], name="res_run_interp_idx"),
            models.Index(fields=["target_key", "completed_at"], name="res_run_target_idx"),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.warning_codes, list):
            raise ValidationError({"warning_codes": "warning_codes must be a list"})
        if not isinstance(self.stats, dict):
            raise ValidationError({"stats": "stats must be an object"})

    def __str__(self):
        return self.resolution_ref


class ResolutionAssertionRow(models.Model):
    run = models.ForeignKey(
        ResolutionRun,
        on_delete=models.CASCADE,
        related_name="assertion_rows",
    )
    assertion_ref = models.CharField(max_length=255, unique=True)
    ordinal = models.PositiveIntegerField()
    candidate_ref = models.CharField(max_length=255, db_index=True)
    kind = models.CharField(max_length=24, choices=ASSERTION_KIND_CHOICES)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES)
    canonical_domain = models.CharField(max_length=120, blank=True)
    canonical_object_ref = models.CharField(max_length=255, blank=True)
    predicate = models.CharField(max_length=120, blank=True)
    semantic_fingerprint = models.CharField(max_length=128, blank=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "resolver_assertion"
        ordering = ["run", "ordinal"]
        constraints = [
            models.UniqueConstraint(fields=["run", "ordinal"], name="res_assertion_ordinal_uq"),
            models.CheckConstraint(condition=Q(ordinal__gte=1), name="res_assertion_ordinal_gte_1"),
            models.CheckConstraint(
                condition=(
                    Q(canonical_domain="", canonical_object_ref="")
                    | (~Q(canonical_domain="") & ~Q(canonical_object_ref=""))
                ),
                name="res_assertion_canonical_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["run", "kind", "ordinal"], name="res_assertion_kind_idx"),
            models.Index(
                fields=["canonical_domain", "canonical_object_ref", "predicate"],
                name="res_assertion_fact_lookup_idx",
            ),
        ]

    def __str__(self):
        return self.assertion_ref
