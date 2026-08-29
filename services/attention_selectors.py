from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, can
from journeys.collaboration_models import (
    JourneyArtifactReviewStatus,
    JourneyBlockerSeverity,
    JourneyBlockerStatus,
    JourneyStepStatus,
)
from journeys.models import Journey, WorkflowKind
from opportunities.models import (
    OpportunityPublicationStatus,
    OpportunitySourceStatus,
    OpportunitySubmissionStatus,
)
from payments.models import PaymentEvidenceStatus, PaymentObligationStatus
from requirements.contracts import RequirementAssessmentState

from .models import ServiceCurrentOutcome, ServiceRequirementEvidenceStatus, ServiceSubmissionStatus
from .selectors import service_journeys_visible_to


ACTIONABLE_STEP_STATUSES = {
    JourneyStepStatus.PENDING,
    JourneyStepStatus.READY,
    JourneyStepStatus.IN_PROGRESS,
    JourneyStepStatus.BLOCKED,
}


def _service_attention_q(*, now):
    """DB-first equivalent of the T34A consequence sources plus Services facts."""
    return (
        Q(steps__status=JourneyStepStatus.READY)
        | Q(
            steps__due_at__lt=now,
            steps__status__in=ACTIONABLE_STEP_STATUSES,
        )
        | Q(blockers__status=JourneyBlockerStatus.ACTIVE)
        | Q(payment_obligations__status__in={PaymentObligationStatus.PENDING, PaymentObligationStatus.PROCESSING})
        | Q(payment_obligations__evidence__status=PaymentEvidenceStatus.REJECTED)
        | Q(service_context__submissions__status=ServiceSubmissionStatus.FAILED)
        | Q(service_context__current_outcome=ServiceCurrentOutcome.ACTION_REQUIRED)
        | Q(service_context__opportunity__publication_status=OpportunityPublicationStatus.WITHDRAWN)
        | Q(
            service_context__opportunity__current_revision__version__gt=F(
                "service_context__opportunity_revision__version"
            )
        )
        | Q(
            service_context__requirement_assessments__status=RequirementAssessmentState.PENDING,
            service_context__requirement_assessments__payment_obligation_links__obligation__status__in={
                PaymentObligationStatus.PENDING,
                PaymentObligationStatus.PROCESSING,
                PaymentObligationStatus.EXPIRED,
                PaymentObligationStatus.CANCELLED,
                PaymentObligationStatus.REFUNDED,
            },
        )
        | Q(
            service_context__requirement_assessments__status=RequirementAssessmentState.PENDING,
            service_context__requirement_assessments__evidence__status=ServiceRequirementEvidenceStatus.SUBMITTED,
        )
        | Q(
            service_context__requirement_assessments__status=RequirementAssessmentState.PENDING,
            service_context__requirement_assessments__step_links__journey_step__status__in=ACTIONABLE_STEP_STATUSES,
        )
    )


def participant_service_attention_journeys(profile, *, now=None):
    now = now or timezone.now()
    if not getattr(profile, "is_authenticated", False):
        return Journey.objects.none()
    return (
        Journey.objects.filter(
            beneficiary=profile,
            workflow=WorkflowKind.SERVICE,
        )
        .filter(
            _service_attention_q(now=now)
            | Q(expires_at__isnull=False, expires_at__lte=now + timedelta(days=7), expires_at__gt=now)
        )
        .select_related("activity", "activity__space", "beneficiary", "service_context")
        .distinct()
    )


def facilitator_attention_journeys(profile, *, now=None):
    now = now or timezone.now()
    visible = service_journeys_visible_to(profile)
    attention = (
        Q(
            steps__due_at__lt=now,
            steps__status__in=ACTIONABLE_STEP_STATUSES,
        )
        | Q(
            blockers__status=JourneyBlockerStatus.ACTIVE,
            blockers__severity__in={JourneyBlockerSeverity.HIGH, JourneyBlockerSeverity.CRITICAL},
        )
        | Q(
            artifacts__reviews__reviewer=profile,
            artifacts__reviews__status__in={JourneyArtifactReviewStatus.REQUESTED, JourneyArtifactReviewStatus.IN_PROGRESS},
        )
        | Q(service_context__submissions__status=ServiceSubmissionStatus.FAILED)
        | Q(service_context__current_outcome=ServiceCurrentOutcome.ACTION_REQUIRED)
        | Q(
            service_context__opportunity__current_revision__version__gt=F(
                "service_context__opportunity_revision__version"
            )
        )
    )
    queryset = visible.filter(attention)
    # PaymentEvidence remains permission-gated without one resolver call per Activity.
    payment_activity_ids = activity_ids_with_permission(
        profile,
        PermissionCode.ACTIVITY_SERVICES_PAYMENT_EVIDENCE_VERIFY,
        at=now,
    )
    payment_scope = visible
    if payment_activity_ids is not None:
        payment_scope = payment_scope.filter(activity_id__in=payment_activity_ids)
    queryset = queryset | payment_scope.filter(
        payment_obligations__evidence__status=PaymentEvidenceStatus.SUBMITTED,
    )
    return queryset.distinct()


def manager_attention_journeys(profile, *, now=None):
    now = now or timezone.now()
    visible = service_journeys_visible_to(profile)
    return (
        visible.filter(
            Q(assignments__isnull=True)
            | Q(blockers__status=JourneyBlockerStatus.ACTIVE)
            | Q(steps__due_at__lt=now, steps__status__in=ACTIONABLE_STEP_STATUSES)
            | Q(
                artifacts__reviews__status__in={
                    JourneyArtifactReviewStatus.REQUESTED,
                    JourneyArtifactReviewStatus.IN_PROGRESS,
                }
            )
            | Q(payment_obligations__evidence__status=PaymentEvidenceStatus.SUBMITTED)
            | Q(service_context__submissions__status=ServiceSubmissionStatus.FAILED)
        )
        .distinct()
    )


def opportunity_curator_attention(profile):
    """Return querysets for the T35 Opportunity staff console without exposing private case data."""
    from opportunities.models import Opportunity, OpportunitySource, OpportunitySubmission

    if not getattr(profile, "is_authenticated", False):
        return {
            "submissions": OpportunitySubmission.objects.none(),
            "sources": OpportunitySource.objects.none(),
            "withdrawn_with_active_journeys": Opportunity.objects.none(),
        }
    submissions = OpportunitySubmission.objects.none()
    if can(profile, PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS):
        submissions = OpportunitySubmission.objects.filter(
            status__in={OpportunitySubmissionStatus.PENDING, OpportunitySubmissionStatus.UNDER_REVIEW}
        ).select_related("submitted_by")
    sources = OpportunitySource.objects.none()
    if can(profile, PermissionCode.OPPORTUNITIES_SOURCES_VERIFY):
        sources = OpportunitySource.objects.filter(
            status__in={OpportunitySourceStatus.CHANGED, OpportunitySourceStatus.UNREACHABLE}
        ).select_related("opportunity")
    withdrawn = Opportunity.objects.none()
    if can(profile, PermissionCode.OPPORTUNITIES_MANAGE):
        withdrawn = Opportunity.objects.filter(
            publication_status=OpportunityPublicationStatus.WITHDRAWN,
            service_contexts__journey__workflow=WorkflowKind.SERVICE,
        ).distinct()
    return {
        "submissions": submissions,
        "sources": sources,
        "withdrawn_with_active_journeys": withdrawn,
    }
