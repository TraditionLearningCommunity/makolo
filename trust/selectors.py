from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.utils import timezone

from activities.models import OccurrenceStatus
from authorization.constants import PermissionCode
from authorization.services import can
from journeys.models import JourneyStatus

from .models import Dispute, Feedback, Proof, Report, VerificationClaim, VerificationDisclosure, VerificationStatus
from .services import can_view_space_trust


PUBLIC_FEEDBACK_BREAKDOWN_MIN_SAMPLE = 3
DEFAULT_RELIABILITY_PERIOD_DAYS = 365


def active_public_verifications_for_space(space, *, at=None):
    at = at or timezone.now()
    return VerificationClaim.objects.filter(
        subject_space=space,
        status=VerificationStatus.VERIFIED,
        disclosure=VerificationDisclosure.PUBLIC_RESULT,
    ).filter(Q(valid_from__isnull=True) | Q(valid_from__lte=at)).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gt=at)
    ).order_by("claim_type", "-reviewed_at")


def _period(period_days, at=None):
    at = at or timezone.now()
    return at - timedelta(days=period_days), at


def get_operational_reliability_summary(space, *, period_days=DEFAULT_RELIABILITY_PERIOD_DAYS, at=None):
    start, end = _period(period_days, at)
    occurrences = space.activities.filter(
        occurrences__start_at__gte=start,
        occurrences__start_at__lte=end,
        occurrences__status__in=[OccurrenceStatus.COMPLETED, OccurrenceStatus.CANCELLED],
    ).values("occurrences__status").annotate(count=Count("occurrences", distinct=True))
    occurrence_counts = {row["occurrences__status"]: row["count"] for row in occurrences}
    occurrence_denominator = sum(occurrence_counts.values())

    journeys = space.activities.filter(
        journeys__created_at__gte=start,
        journeys__created_at__lte=end,
        journeys__status__in=[JourneyStatus.FULFILLED, JourneyStatus.CANCELLED],
    ).values("journeys__status").annotate(count=Count("journeys", distinct=True))
    journey_counts = {row["journeys__status"]: row["count"] for row in journeys}
    journey_denominator = sum(journey_counts.values())

    metrics = []
    if occurrence_denominator:
        metrics.append({"key": "occurrence_completion", "numerator": occurrence_counts.get(OccurrenceStatus.COMPLETED, 0), "denominator": occurrence_denominator, "period_days": period_days, "source": "Occurrence.status"})
        metrics.append({"key": "occurrence_cancellation", "numerator": occurrence_counts.get(OccurrenceStatus.CANCELLED, 0), "denominator": occurrence_denominator, "period_days": period_days, "source": "Occurrence.status"})
    if journey_denominator:
        metrics.append({"key": "journey_fulfillment", "numerator": journey_counts.get(JourneyStatus.FULFILLED, 0), "denominator": journey_denominator, "period_days": period_days, "source": "Journey.status"})
    return {"period_days": period_days, "metrics": metrics}


def _feedback_summary(space, *, period_days, at=None):
    start, end = _period(period_days, at)
    aggregate = Feedback.objects.filter(
        journey__activity__space=space,
        withdrawn_at__isnull=True,
        submitted_at__gte=start,
        submitted_at__lte=end,
    ).aggregate(
        sample_size=Count("id"),
        positive=Count("id", filter=Q(overall_sentiment="positive")),
        neutral=Count("id", filter=Q(overall_sentiment="neutral")),
        negative=Count("id", filter=Q(overall_sentiment="negative")),
    )
    result = {
        "verified_experiences": aggregate["sample_size"],
        "period_days": period_days,
        "source": "Feedback anchored to Journey",
        "breakdown_available": aggregate["sample_size"] >= PUBLIC_FEEDBACK_BREAKDOWN_MIN_SAMPLE,
        "minimum_sample": PUBLIC_FEEDBACK_BREAKDOWN_MIN_SAMPLE,
    }
    if result["breakdown_available"]:
        result["sentiment"] = {"positive": aggregate["positive"], "neutral": aggregate["neutral"], "negative": aggregate["negative"]}
    return result


def get_public_trust_summary(space, viewer=None, *, period_days=DEFAULT_RELIABILITY_PERIOD_DAYS, at=None):
    verification = [
        {"claim_type": claim.claim_type, "status": VerificationStatus.VERIFIED, "valid_until": claim.valid_until}
        for claim in active_public_verifications_for_space(space, at=at)
    ]
    return {
        "subject": {"type": "space", "id": str(space.pk), "name": space.name},
        "verification": verification,
        "operations": get_operational_reliability_summary(space, period_days=period_days, at=at),
        "feedback": _feedback_summary(space, period_days=period_days, at=at),
    }


def get_operator_trust_summary(space, viewer, *, period_days=DEFAULT_RELIABILITY_PERIOD_DAYS, at=None):
    if not can_view_space_trust(viewer, space):
        raise PermissionDenied("Accès Trust opérateur refusé.")
    summary = get_public_trust_summary(space, viewer=viewer, period_days=period_days, at=at)
    summary["issues"] = {
        "reports": dict(Report.objects.filter(space=space).values_list("status").annotate(count=Count("id"))),
        "disputes": dict(Dispute.objects.filter(respondent_space=space).values_list("status").annotate(count=Count("id"))),
    }
    return summary


def proofs_for_profile(profile):
    return Proof.objects.filter(subject_profile=profile).select_related("journey__activity", "occurrence").order_by("-issued_at")


def public_proof_by_id(public_id):
    return Proof.objects.filter(public_id=public_id, is_public=True).select_related("subject_profile", "journey__activity", "occurrence").first()


def report_visible_to(report, viewer) -> bool:
    if not getattr(viewer, "is_authenticated", False):
        return False
    if can(viewer, PermissionCode.PLATFORM_TRUST_REVIEW):
        return True
    if report.reporter_id == viewer.pk:
        return True
    return bool(report.space_id and can_view_space_trust(viewer, report.space))


def dispute_visible_to(dispute, viewer) -> bool:
    if not getattr(viewer, "is_authenticated", False):
        return False
    if can(viewer, PermissionCode.PLATFORM_TRUST_REVIEW):
        return True
    if dispute.claimant_id == viewer.pk or dispute.respondent_profile_id == viewer.pk:
        return True
    return bool(dispute.respondent_space_id and can_view_space_trust(viewer, dispute.respondent_space))
