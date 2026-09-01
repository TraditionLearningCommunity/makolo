from django.db.models import Prefetch

from journeys.models import Journey
from payments.models import PaymentObligation


def readiness_queryset(queryset=None):
    """Load canonical facts needed by Readiness with bounded query growth."""
    queryset = queryset if queryset is not None else Journey.objects.all()
    obligations = PaymentObligation.objects.order_by("created_at", "id")
    return (
        queryset.select_related("activity", "occurrence", "beneficiary", "service_context")
        .prefetch_related(
            "requests",
            "steps__assignments",
            "steps__dependencies__depends_on",
            "blockers",
            Prefetch("payment_obligations", queryset=obligations),
            "capacity_reservations__pool",
            "accesses",
            "service_context__requirement_assessments__requirement",
            "service_context__requirement_assessments__step_links__journey_step",
            "service_context__requirement_assessments__payment_obligation_links__obligation",
            "form_requests__form_version__form",
            "form_requests__response",
        )
    )


def participant_readiness_queryset(profile, queryset=None):
    queryset = queryset if queryset is not None else Journey.objects.all()
    if not getattr(profile, "is_authenticated", False):
        return queryset.none()
    return readiness_queryset(queryset.filter(beneficiary=profile))
