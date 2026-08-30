from __future__ import annotations

from dataclasses import dataclass

from payments.models import PaymentObligationStatus
from requirements.contracts import RequirementAssessmentState, RequirementMode

from .transition_models import OPEN_TRANSITION_STATUSES, SubscriptionTransition


@dataclass(frozen=True)
class SubscriptionTransitionProgress:
    total_mandatory: int
    satisfied: int
    pending: int
    unsatisfied: int
    not_applicable: int
    payment_required: bool
    action_required: bool
    needs_review: bool
    waiting_verification: bool


def get_open_subscription_transition(subscription):
    return (
        SubscriptionTransition.objects.filter(
            subscription=subscription,
            status__in=OPEN_TRANSITION_STATUSES,
        )
        .select_related("source_plan_version__plan", "target_plan_version__plan", "source_item")
        .first()
    )


def get_subscription_transition(transition_id):
    return (
        SubscriptionTransition.objects.select_related(
            "subscription__profile",
            "subscription__space",
            "source_plan_version__plan",
            "target_plan_version__plan",
            "source_item",
            "requested_by",
        )
        .prefetch_related(
            "assessments__plan_requirement",
            "assessments__payment_obligation_links__obligation",
        )
        .get(pk=transition_id)
    )


def get_transition_progress(transition):
    assessments = list(
        transition.assessments.select_related("plan_requirement")
        .prefetch_related("payment_obligation_links__obligation")
        .order_by("plan_requirement__position", "id")
    )
    mandatory = [item for item in assessments if item.plan_requirement.is_mandatory]
    counts = {
        RequirementAssessmentState.SATISFIED: 0,
        RequirementAssessmentState.PENDING: 0,
        RequirementAssessmentState.UNSATISFIED: 0,
        RequirementAssessmentState.NOT_APPLICABLE: 0,
    }
    for assessment in mandatory:
        if assessment.state in counts:
            counts[assessment.state] += 1
        elif assessment.state == RequirementAssessmentState.UNASSESSED:
            counts[RequirementAssessmentState.PENDING] += 1

    payment_required = False
    action_required = False
    needs_review = False
    waiting_verification = False
    for assessment in mandatory:
        if assessment.state in {RequirementAssessmentState.SATISFIED, RequirementAssessmentState.NOT_APPLICABLE}:
            continue
        mode = assessment.plan_requirement.mode
        if mode == RequirementMode.PAYMENT:
            obligations = [link.obligation for link in assessment.payment_obligation_links.all()]
            payment_required = not obligations or any(
                obligation.status not in {PaymentObligationStatus.SATISFIED, PaymentObligationStatus.WAIVED}
                for obligation in obligations
            )
        elif mode == RequirementMode.ACTION:
            action_required = True
        elif mode == RequirementMode.REVIEW:
            needs_review = True
        elif mode in {RequirementMode.VERIFICATION, RequirementMode.EXTERNAL_CHECK}:
            waiting_verification = True

    return SubscriptionTransitionProgress(
        total_mandatory=len(mandatory),
        satisfied=counts[RequirementAssessmentState.SATISFIED],
        pending=counts[RequirementAssessmentState.PENDING],
        unsatisfied=counts[RequirementAssessmentState.UNSATISFIED],
        not_applicable=counts[RequirementAssessmentState.NOT_APPLICABLE],
        payment_required=payment_required,
        action_required=action_required,
        needs_review=needs_review,
        waiting_verification=waiting_verification,
    )
