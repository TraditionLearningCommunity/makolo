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
    policy_context = models.JSONField(default=dict, blank=True)
    observation_hints = models.JSONField(default=dict, blank=True)
    claim_token = models.UUIDField(null=True, blank=True, db_index=True)
    claimed_by = models.CharField(max_length=120, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
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
