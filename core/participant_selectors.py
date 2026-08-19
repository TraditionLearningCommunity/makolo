from django.db.models import Q
from django.utils import timezone

from access.models import Access, AccessStatus
from commerce.models import CommerceOrder
from journeys.models import Journey, JourneyStatus


ACTIVE_JOURNEY_STATUSES = {
    JourneyStatus.DRAFT,
    JourneyStatus.SUBMITTED,
    JourneyStatus.PENDING_APPROVAL,
    JourneyStatus.APPROVED,
    JourneyStatus.PENDING_PAYMENT,
    JourneyStatus.CONFIRMED,
}
ACTIONABLE_JOURNEY_STATUSES = {
    JourneyStatus.DRAFT,
    JourneyStatus.PENDING_APPROVAL,
    JourneyStatus.PENDING_PAYMENT,
}
HISTORY_JOURNEY_STATUSES = {
    JourneyStatus.FULFILLED,
    JourneyStatus.REJECTED,
    JourneyStatus.CANCELLED,
    JourneyStatus.EXPIRED,
}
ACTIVE_ACCESS_STATUSES = {AccessStatus.PENDING, AccessStatus.VALID}
HISTORY_ACCESS_STATUSES = {
    AccessStatus.USED,
    AccessStatus.CANCELLED,
    AccessStatus.REVOKED,
    AccessStatus.EXPIRED,
    AccessStatus.TRANSFERRED,
}


def _authenticated(profile):
    return bool(getattr(profile, "is_authenticated", False))


def participant_journeys(profile):
    if not _authenticated(profile):
        return Journey.objects.none()
    return (
        Journey.objects.filter(beneficiary=profile)
        .select_related("activity", "activity__event_vertical", "occurrence")
        .prefetch_related(
            "occurrence__place_links__place",
            "requests",
            "transitions",
            "accesses__credentials",
            "commerce_orders__items__offer",
        )
    )


def participant_actionable_journeys(profile):
    return participant_journeys(profile).filter(status__in=ACTIONABLE_JOURNEY_STATUSES)


def participant_active_journeys(profile):
    return participant_journeys(profile).filter(status__in=ACTIVE_JOURNEY_STATUSES)


def participant_history_journeys(profile):
    return participant_journeys(profile).filter(status__in=HISTORY_JOURNEY_STATUSES)


def participant_orders(profile):
    if not _authenticated(profile):
        return CommerceOrder.objects.none()
    return (
        CommerceOrder.objects.filter(buyer=profile)
        .select_related("journey", "journey__activity", "journey__occurrence")
        .prefetch_related("items__offer")
    )


def participant_accesses(profile):
    if not _authenticated(profile):
        return Access.objects.none()
    return (
        Access.objects.filter(beneficiary=profile)
        .select_related("activity", "activity__event_vertical", "occurrence", "journey")
        .prefetch_related("occurrence__place_links__place", "credentials")
    )


def participant_active_accesses(profile):
    return participant_accesses(profile).filter(status__in=ACTIVE_ACCESS_STATUSES)


def participant_upcoming_accesses(profile, *, at=None):
    at = at or timezone.now()
    return participant_active_accesses(profile).filter(
        Q(occurrence__isnull=True)
        | Q(occurrence__end_at__gte=at)
        | Q(occurrence__end_at__isnull=True, occurrence__start_at__gte=at)
    ).order_by("occurrence__start_at", "-created_at")


def participant_access_history(profile):
    return participant_accesses(profile).filter(status__in=HISTORY_ACCESS_STATUSES)


def participant_upcoming_occurrences(profile, *, at=None):
    at = at or timezone.now()
    return (
        participant_journeys(profile)
        .filter(occurrence__isnull=False, occurrence__start_at__gte=at)
        .order_by("occurrence__start_at")
    )
