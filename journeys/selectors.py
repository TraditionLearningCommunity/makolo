from django.db.models import Q

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission

from .models import Journey, JourneyStatus


def journeys_for_profile(profile):
    if not getattr(profile, "is_authenticated", False):
        return Journey.objects.none()
    return (
        Journey.objects.filter(Q(beneficiary=profile) | Q(initiated_by=profile))
        .select_related("activity", "occurrence", "beneficiary", "initiated_by")
        .distinct()
    )


def journey_with_requests(journey_id):
    return (
        Journey.objects.select_related("activity", "occurrence", "beneficiary", "initiated_by")
        .prefetch_related("requests__requester", "requests__decided_by")
        .get(pk=journey_id)
    )


def journeys_for_activity_manager(profile, activity=None):
    queryset = Journey.objects.select_related("activity", "occurrence", "beneficiary", "initiated_by")
    if activity is not None:
        allowed = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_REQUESTS_VIEW)
        if allowed is not None and activity.pk not in allowed:
            return queryset.none()
        return queryset.filter(activity=activity)
    allowed = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_REQUESTS_VIEW)
    if allowed is None:
        return queryset
    return queryset.filter(activity_id__in=allowed)


def pending_approval_journeys(profile=None, activity=None):
    queryset = Journey.objects.filter(status=JourneyStatus.PENDING_APPROVAL).select_related(
        "activity", "occurrence", "beneficiary", "initiated_by"
    )
    if profile is not None:
        allowed = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_REQUESTS_VIEW)
        if allowed is not None:
            queryset = queryset.filter(activity_id__in=allowed)
    if activity is not None:
        queryset = queryset.filter(activity=activity)
    return queryset


def journey_for_ticket_order(order):
    if not getattr(order, "journey_id", None):
        return None
    return (
        Journey.objects.select_related("activity", "occurrence", "beneficiary", "initiated_by")
        .prefetch_related("requests")
        .filter(pk=order.journey_id)
        .first()
    )
