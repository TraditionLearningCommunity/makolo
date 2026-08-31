from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone

from journeys.models import (
    Journey,
    JourneyArtifactReview,
    JourneyArtifactReviewStatus,
    JourneyAssignment,
    JourneyAssignmentStatus,
    JourneyBlocker,
    JourneyStep,
    JourneyStepStatus,
    JourneyStatus,
    WorkflowKind,
)
from payments.models import (
    Payment,
    PaymentEvidence,
    PaymentEvidenceStatus,
    PaymentObligation,
    PaymentObligationProcessingMode,
    PaymentStatus,
)
from services.models import (
    ServiceCurrentOutcome,
    ServiceDetails,
    ServiceJourneyContext,
    ServiceOutcomeEvent,
    ServiceSubmission,
)


TERMINAL_JOURNEY_STATUSES = {
    JourneyStatus.FULFILLED,
    JourneyStatus.REJECTED,
    JourneyStatus.CANCELLED,
    JourneyStatus.EXPIRED,
}


def _percent(numerator, denominator):
    if not denominator:
        return None
    return round((numerator / denominator) * 100, 1)


def _choice_counts(queryset, field, choices):
    rows = queryset.values(field).annotate(total=Count("id"))
    counts = {row[field]: row["total"] for row in rows}
    return {value: counts.get(value, 0) for value in choices}


def _service_journeys(activity):
    if not ServiceDetails.objects.filter(activity_id=activity.pk).exists():
        raise ValueError("Service analytics require an Activity with ServiceDetails.")
    return Journey.objects.filter(activity_id=activity.pk, workflow=WorkflowKind.SERVICE)


def service_activity_summary(activity, *, include_financials=False, now=None):
    """Build the privacy-safe transactional read model for one Service Activity.

    Percentages intentionally carry their numerator and denominator so the UI
    cannot present an unexplained rate. Monetary values are omitted unless the
    caller has already established the canonical financial analytics permission.
    """

    now = now or timezone.now()
    journeys = _service_journeys(activity)
    total_journeys = journeys.count()
    started_journeys = journeys.filter(started_at__isnull=False).count()
    fulfilled_journeys = journeys.filter(
        started_at__isnull=False,
        fulfilled_at__isnull=False,
        fulfilled_at__gte=F("started_at"),
    ).count()

    fulfillment_duration = ExpressionWrapper(
        F("fulfilled_at") - F("started_at"), output_field=DurationField()
    )
    fulfillment_duration_rows = journeys.filter(
        started_at__isnull=False,
        fulfilled_at__isnull=False,
        fulfilled_at__gte=F("started_at"),
    )
    average_fulfillment = fulfillment_duration_rows.aggregate(
        value=Avg(fulfillment_duration)
    )["value"]

    contexts = ServiceJourneyContext.objects.filter(journey__in=journeys)
    external_decided = contexts.filter(
        current_outcome__in=[
            ServiceCurrentOutcome.SUCCESSFUL,
            ServiceCurrentOutcome.UNSUCCESSFUL,
        ]
    ).count()
    external_successful = contexts.filter(
        current_outcome=ServiceCurrentOutcome.SUCCESSFUL
    ).count()

    steps = JourneyStep.objects.filter(journey__in=journeys)
    step_duration = ExpressionWrapper(
        F("completed_at") - F("started_at"), output_field=DurationField()
    )
    step_duration_rows = (
        steps.filter(
            started_at__isnull=False,
            completed_at__isnull=False,
            completed_at__gte=F("started_at"),
        )
        .values("kind")
        .annotate(count=Count("id"), average=Avg(step_duration))
        .order_by("kind")
    )
    current_overdue = steps.filter(
        due_at__lt=now,
    ).exclude(status__in=[
        JourneyStepStatus.COMPLETED,
        JourneyStepStatus.SKIPPED,
        JourneyStepStatus.CANCELLED,
    ]).count()
    completed_late = steps.filter(
        status=JourneyStepStatus.COMPLETED,
        due_at__isnull=False,
        completed_at__isnull=False,
        completed_at__gt=F("due_at"),
    ).count()

    blockers = JourneyBlocker.objects.filter(journey__in=journeys)
    blocker_statuses = _choice_counts(
        blockers,
        "status",
        ["active", "resolved", "waived"],
    )
    blocker_categories = {
        row["category"]: row["total"]
        for row in blockers.values("category").annotate(total=Count("id")).order_by("category")
    }
    blocker_severities = {
        row["severity"]: row["total"]
        for row in blockers.values("severity").annotate(total=Count("id")).order_by("severity")
    }

    opportunity_contexts = contexts.filter(opportunity__isnull=False)
    journeys_with_opportunity = opportunity_contexts.values("journey_id").distinct().count()
    opportunities_with_journey = opportunity_contexts.values("opportunity_id").distinct().count()

    submissions = ServiceSubmission.objects.filter(context__in=contexts)
    journeys_with_submission = submissions.values("context__journey_id").distinct().count()
    submission_statuses = {
        row["status"]: row["total"]
        for row in submissions.values("status").annotate(total=Count("id")).order_by("status")
    }

    current_outcomes = {
        row["current_outcome"]: row["total"]
        for row in contexts.values("current_outcome")
        .annotate(total=Count("id"))
        .order_by("current_outcome")
    }
    outcome_history = {
        row["event_type"]: row["total"]
        for row in ServiceOutcomeEvent.objects.filter(context__in=contexts)
        .values("event_type")
        .annotate(total=Count("id"))
        .order_by("event_type")
    }

    assignments = JourneyAssignment.objects.filter(journey__in=journeys)
    active_assignments = assignments.filter(status=JourneyAssignmentStatus.ACTIVE)
    assignment_by_responsibility = {
        row["responsibility"]: row["total"]
        for row in active_assignments.values("responsibility")
        .annotate(total=Count("id"))
        .order_by("responsibility")
    }
    active_assigned_journeys = active_assignments.exclude(
        journey__status__in=TERMINAL_JOURNEY_STATUSES
    ).values("journey_id").distinct().count()

    reviews = JourneyArtifactReview.objects.filter(artifact__journey__in=journeys)
    review_statuses = _choice_counts(
        reviews,
        "status",
        JourneyArtifactReviewStatus.values,
    )
    review_turnaround = ExpressionWrapper(
        F("decided_at") - F("requested_at"), output_field=DurationField()
    )
    decided_reviews = reviews.filter(
        decided_at__isnull=False,
        decided_at__gte=F("requested_at"),
    )
    average_review_turnaround = decided_reviews.aggregate(value=Avg(review_turnaround))["value"]

    obligations = PaymentObligation.objects.filter(journey__in=journeys)
    obligation_statuses = {
        row["status"]: row["total"]
        for row in obligations.values("status").annotate(total=Count("id")).order_by("status")
    }
    obligation_modes = {
        row["processing_mode"]: row["total"]
        for row in obligations.values("processing_mode")
        .annotate(total=Count("id"))
        .order_by("processing_mode")
    }

    provider_payments = Payment.objects.filter(
        obligation__in=obligations,
        obligation__processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
    )
    external_evidence = PaymentEvidence.objects.filter(
        obligation__in=obligations,
        obligation__processing_mode=PaymentObligationProcessingMode.EXTERNAL,
    )

    financials = None
    if include_financials:
        financials = {
            "obligations_by_currency": [
                {
                    "currency": row["currency"],
                    "amount": row["amount"] or 0,
                }
                for row in obligations.values("currency")
                .annotate(amount=Sum("amount"))
                .order_by("currency")
            ],
            "provider_payments_by_currency": [
                {
                    "currency": row["currency"],
                    "amount": row["amount"] or 0,
                }
                for row in provider_payments.filter(status=PaymentStatus.SUCCEEDED)
                .values("currency")
                .annotate(amount=Sum("amount"))
                .order_by("currency")
            ],
        }

    return {
        "journeys": {
            "volume": total_journeys,
            "start_rate": {
                "numerator": started_journeys,
                "denominator": total_journeys,
                "percent": _percent(started_journeys, total_journeys),
                "definition": "journeys_started / journeys_created",
            },
            "makolo_fulfillment_rate": {
                "numerator": fulfilled_journeys,
                "denominator": started_journeys,
                "percent": _percent(fulfilled_journeys, started_journeys),
                "definition": "journeys_fulfilled / journeys_started",
            },
            "external_success_rate": {
                "numerator": external_successful,
                "denominator": external_decided,
                "percent": _percent(external_successful, external_decided),
                "definition": "current_outcome_successful / current_outcome_decided",
            },
            "time_to_fulfillment": {
                "count": fulfillment_duration_rows.count(),
                "average": average_fulfillment,
                "definition": "started_at -> fulfilled_at",
            },
        },
        "steps": {
            "duration_by_kind": list(step_duration_rows),
            "currently_overdue": current_overdue,
            "completed_late": completed_late,
        },
        "blockers": {
            "by_status": blocker_statuses,
            "by_category": blocker_categories,
            "by_severity": blocker_severities,
        },
        "opportunity_funnel": {
            "journeys_with_opportunity": journeys_with_opportunity,
            "opportunities_with_journey": opportunities_with_journey,
        },
        "submissions": {
            "journeys_with_submission": journeys_with_submission,
            "attempts": submissions.count(),
            "by_status": submission_statuses,
        },
        "outcomes": {
            "current": current_outcomes,
            "history": outcome_history,
        },
        "workload": {
            "active_assignments_by_responsibility": assignment_by_responsibility,
            "active_assigned_journeys": active_assigned_journeys,
        },
        "reviews": {
            "by_status": review_statuses,
            "decided_count": decided_reviews.count(),
            "average_turnaround": average_review_turnaround,
        },
        "payments": {
            "obligations_by_status": obligation_statuses,
            "obligations_by_mode": obligation_modes,
            "provider_payment_attempts": provider_payments.count(),
            "provider_payment_failed": provider_payments.filter(status=PaymentStatus.FAILED).count(),
            "external_evidence_by_status": _choice_counts(
                external_evidence,
                "status",
                PaymentEvidenceStatus.values,
            ),
            "financials": financials,
        },
    }
