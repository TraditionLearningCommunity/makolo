from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from requirements.contracts import RequirementAssessmentState, RequirementMode

from .authorization import require_subscription_review_permission
from .transition_models import SubscriptionRequirementAssessment
from .transition_services import record_transition_requirement_decision


@transaction.atomic
def review_subscription_requirement(*, actor, assessment_id, state, reason_code, note=""):
    """Record a platform-authorized human review with serialization.

    Only pending/unassessed review-mode assessments can receive a decision. The row
    lock makes concurrent reviewers observe the first committed decision instead of
    silently overwriting it.
    """
    require_subscription_review_permission(actor)
    assessment = (
        SubscriptionRequirementAssessment.objects.select_for_update()
        .select_related("plan_requirement", "transition", "transition__subscription")
        .get(pk=assessment_id)
    )
    if assessment.plan_requirement.mode != RequirementMode.REVIEW:
        raise ValidationError("Cet Assessment n'est pas une review humaine.")
    if assessment.state not in {RequirementAssessmentState.UNASSESSED, RequirementAssessmentState.PENDING}:
        raise ValidationError("Cette review a déjà reçu une décision terminale.")
    if state not in {
        RequirementAssessmentState.SATISFIED,
        RequirementAssessmentState.UNSATISFIED,
        RequirementAssessmentState.NOT_APPLICABLE,
    }:
        raise ValidationError("Décision de review invalide.")
    return record_transition_requirement_decision(
        assessment=assessment,
        state=state,
        actor=actor,
        reason_code=reason_code,
        note=note,
    )
