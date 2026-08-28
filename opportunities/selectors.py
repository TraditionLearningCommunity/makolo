from django.db.models import Q
from django.utils import timezone

from .models import Opportunity, OpportunityPublicationStatus, OpportunitySave


def published_opportunities():
    return (
        Opportunity.objects.filter(
            publication_status=OpportunityPublicationStatus.PUBLISHED,
            current_revision__published_at__isnull=False,
        )
        .select_related("current_revision")
        .order_by("current_revision__deadline_at", "-published_at", "id")
    )


def upcoming_opportunities(*, at=None):
    at = at or timezone.now()
    return published_opportunities().filter(current_revision__opens_at__gt=at)


def open_opportunities(*, at=None):
    at = at or timezone.now()
    return published_opportunities().filter(
        Q(current_revision__opens_at__isnull=True) | Q(current_revision__opens_at__lte=at),
        Q(current_revision__deadline_at__isnull=True) | Q(current_revision__deadline_at__gt=at),
    )


def closed_opportunities(*, at=None):
    at = at or timezone.now()
    return published_opportunities().filter(current_revision__deadline_at__lte=at)


def opportunities_by_kind(kind, *, queryset=None):
    queryset = queryset if queryset is not None else published_opportunities()
    return queryset.filter(kind=kind)


def opportunities_for_zone(zone, *, role=None, queryset=None):
    queryset = queryset if queryset is not None else published_opportunities()
    filters = {"current_revision__zones__zone": zone}
    if role:
        filters["current_revision__zones__role"] = role
    return queryset.filter(**filters).distinct()


def saved_opportunities(profile):
    if not getattr(profile, "is_authenticated", False):
        return Opportunity.objects.none()
    ids = OpportunitySave.objects.filter(profile=profile).values_list("opportunity_id", flat=True)
    return Opportunity.objects.filter(pk__in=ids).select_related("current_revision").order_by("-published_at", "id")


def submission_for_owner(*, submission_id, profile):
    from .models import OpportunitySubmission
    if not getattr(profile, "is_authenticated", False):
        return None
    return OpportunitySubmission.objects.filter(pk=submission_id, submitted_by=profile).first()
