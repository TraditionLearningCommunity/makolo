from __future__ import annotations

from django.db import models
from django.db.models import Q

from prospector.frontier import FrontierState


FRONTIER_STATUS_CHOICES = [
    (FrontierState.READY.value, "Ready"),
    (FrontierState.CLAIMED.value, "Claimed"),
    (FrontierState.COMPLETED.value, "Completed"),
    (FrontierState.SUPPRESSED.value, "Suppressed"),
]


class ProspectorFrontierEntry(models.Model):
    target_key = models.CharField(max_length=96, unique=True)
    kind = models.CharField(max_length=64)
    locator = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=FRONTIER_STATUS_CHOICES,
        default=FrontierState.READY.value,
    )
    priority = models.PositiveIntegerField(default=100)
    available_at = models.DateTimeField(db_index=True)
    first_discovered_at = models.DateTimeField()
    last_discovered_at = models.DateTimeField()
    discovery_count = models.PositiveBigIntegerField(default=1)
    handoff_generation = models.PositiveBigIntegerField(default=1)
    policy_context = models.JSONField(default=dict, blank=True)
    observation_hints = models.JSONField(default=dict, blank=True)
    claim_token = models.UUIDField(null=True, blank=True, db_index=True)
    claimed_by = models.CharField(max_length=120, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    suppressed_at = models.DateTimeField(null=True, blank=True)
    suppression_reason = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prospector_frontier_entry"
        ordering = ["priority", "available_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(discovery_count__gte=1),
                name="pros_frontier_count_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(handoff_generation__gte=1),
                name="pros_frontier_handoff_gen_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(
                            status=FrontierState.CLAIMED.value,
                            claim_token__isnull=False,
                            claimed_at__isnull=False,
                            lease_expires_at__isnull=False,
                        )
                        & ~Q(claimed_by="")
                    )
                    | (
                        ~Q(status=FrontierState.CLAIMED.value)
                        & Q(
                            claim_token__isnull=True,
                            claimed_by="",
                            claimed_at__isnull=True,
                            lease_expires_at__isnull=True,
                        )
                    )
                ),
                name="pros_frontier_claim_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=FrontierState.COMPLETED.value,
                        completed_at__isnull=False,
                    )
                    | ~Q(status=FrontierState.COMPLETED.value)
                ),
                name="pros_frontier_completed_at",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(
                            status=FrontierState.SUPPRESSED.value,
                            suppressed_at__isnull=False,
                        )
                        & ~Q(suppression_reason="")
                    )
                    | (
                        ~Q(status=FrontierState.SUPPRESSED.value)
                        & Q(
                            suppressed_at__isnull=True,
                            suppression_reason="",
                        )
                    )
                ),
                name="pros_frontier_suppression_consistent",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "available_at", "priority", "id"],
                name="pros_frontier_ready_idx",
            ),
            models.Index(
                fields=["last_discovered_at", "id"],
                name="pros_frontier_seen_idx",
            ),
            models.Index(
                fields=["status", "lease_expires_at", "priority", "id"],
                name="pros_frontier_lease_idx",
            ),
        ]

    def __str__(self):
        return f"{self.target_key} [{self.status}]"


class ProspectorFrontierEvidence(models.Model):
    frontier_entry = models.ForeignKey(
        ProspectorFrontierEntry,
        on_delete=models.CASCADE,
        related_name="evidence_rows",
    )
    evidence_key = models.CharField(max_length=64)
    method = models.CharField(max_length=80)
    source_target_key = models.CharField(max_length=128, blank=True)
    source_observation_ref = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=160, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    policy_context = models.JSONField(default=dict, blank=True)
    observation_hints = models.JSONField(default=dict, blank=True)
    first_discovered_at = models.DateTimeField()
    last_discovered_at = models.DateTimeField()
    discovery_count = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prospector_frontier_evidence"
        ordering = ["first_discovered_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["frontier_entry", "evidence_key"],
                name="pros_evidence_entry_key_uq",
            ),
            models.CheckConstraint(
                condition=Q(discovery_count__gte=1),
                name="pros_evidence_count_gte_1",
            ),
        ]
        indexes = [
            models.Index(
                fields=["source_target_key", "id"],
                name="pros_evidence_source_idx",
            )
        ]

    def __str__(self):
        return f"{self.frontier_entry_id}:{self.method}:{self.evidence_key[:12]}"


class ProspectorSourceCheckpoint(models.Model):
    source_name = models.CharField(max_length=120)
    mission_key = models.CharField(max_length=160)
    mission_fingerprint = models.CharField(max_length=64)
    source_revision = models.CharField(max_length=120)
    cursor = models.JSONField(default=dict, blank=True)
    exhausted = models.BooleanField(default=False)
    checkpoint_updated_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prospector_source_checkpoint"
        constraints = [
            models.UniqueConstraint(
                fields=["source_name", "mission_key"],
                name="pros_source_checkpoint_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["source_name", "exhausted", "updated_at"],
                name="pros_source_progress_idx",
            )
        ]

    def __str__(self):
        return f"{self.source_name}:{self.mission_key}"



class ProspectorBudgetCounter(models.Model):
    policy_key = models.CharField(max_length=120)
    scope_kind = models.CharField(max_length=32)
    scope_key = models.CharField(max_length=255)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    used_count = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prospector_budget_counter"
        constraints = [
            models.UniqueConstraint(
                fields=["policy_key", "scope_kind", "scope_key", "period_start"],
                name="pros_budget_counter_scope_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["policy_key", "period_end", "scope_kind"],
                name="pros_budget_counter_period_idx",
            )
        ]

    def __str__(self):
        return f"{self.policy_key}:{self.scope_kind}:{self.scope_key}:{self.used_count}"


class ProspectorBudgetReservation(models.Model):
    handoff_key = models.CharField(max_length=96)
    policy_key = models.CharField(max_length=120)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    scopes = models.JSONField(default=dict)
    limits = models.JSONField(default=dict)
    reserved_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prospector_budget_reservation"
        constraints = [
            models.UniqueConstraint(
                fields=["handoff_key", "policy_key", "period_start"],
                name="pros_budget_reservation_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["policy_key", "period_end"],
                name="pros_budget_resv_period_idx",
            )
        ]

    def __str__(self):
        return f"{self.policy_key}:{self.handoff_key}"



class ProspectorFeedbackEvent(models.Model):
    event_key = models.CharField(max_length=160, unique=True)
    target_key = models.CharField(max_length=96, db_index=True)
    signal = models.CharField(max_length=40)
    producer = models.CharField(max_length=40)
    source_ref = models.CharField(max_length=255)
    occurred_at = models.DateTimeField()
    scopes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prospector_feedback_event"
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["target_key", "occurred_at", "id"],
                name="pros_fb_event_target_idx",
            )
        ]

    def __str__(self):
        return f"{self.event_key}:{self.signal}"


class ProspectorFeedbackProjection(models.Model):
    policy_key = models.CharField(max_length=120)
    policy_fingerprint = models.CharField(max_length=64)
    last_event_id = models.PositiveBigIntegerField(default=0)
    projected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prospector_feedback_projection"
        constraints = [
            models.UniqueConstraint(
                fields=["policy_key", "policy_fingerprint"],
                name="pros_fb_projection_uq",
            )
        ]

    def __str__(self):
        return f"{self.policy_key}:{self.policy_fingerprint[:12]}:{self.last_event_id}"


class ProspectorFeedbackStat(models.Model):
    policy_fingerprint = models.CharField(max_length=64)
    scope_kind = models.CharField(max_length=32)
    scope_key = models.CharField(max_length=255)
    sample_count = models.PositiveBigIntegerField(default=0)
    score_sum = models.BigIntegerField(default=0)
    positive_count = models.PositiveBigIntegerField(default=0)
    neutral_count = models.PositiveBigIntegerField(default=0)
    negative_count = models.PositiveBigIntegerField(default=0)
    last_feedback_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prospector_feedback_stat"
        constraints = [
            models.UniqueConstraint(
                fields=["policy_fingerprint", "scope_kind", "scope_key"],
                name="pros_fb_stat_scope_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["policy_fingerprint", "scope_kind", "scope_key"],
                name="pros_fb_stat_scope_idx",
            )
        ]

    def __str__(self):
        return (
            f"{self.policy_fingerprint[:12]}:{self.scope_kind}:"
            f"{self.scope_key}:{self.sample_count}"
        )
