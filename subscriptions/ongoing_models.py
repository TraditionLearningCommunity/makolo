from __future__ import annotations

import uuid

from django.db import models

from requirements.contracts import RequirementAssessmentState

from .eligibility_models import PlanRequirement
from .runtime_models import Subscription


class SubscriptionOngoingRequirementState(models.Model):
    """Minimal persisted state for idempotent ongoing Requirement orchestration.

    The canonical Requirement remains PlanRequirement; this row only remembers the
    last evaluated state for one active Subscription so changes can be audited and
    events deduplicated without materializing subject x plan eligibility.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="ongoing_requirement_states",
    )
    plan_requirement = models.ForeignKey(
        PlanRequirement,
        on_delete=models.PROTECT,
        related_name="subscription_ongoing_states",
    )
    state = models.CharField(max_length=20, choices=RequirementAssessmentState.choices)
    reason_code = models.CharField(max_length=160, blank=True)
    first_unsatisfied_at = models.DateTimeField(null=True, blank=True)
    last_evaluated_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["subscription", "plan_requirement__position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "plan_requirement"],
                name="subs_ongoing_requirement_unique",
            )
        ]
        indexes = [
            models.Index(fields=["subscription", "state"], name="subs_ongoing_state_idx"),
        ]
