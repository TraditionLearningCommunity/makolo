from django.db.models import Prefetch, Q
from django.utils import timezone

from activities.models import Occurrence, OccurrencePlace
from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission
from organizations.models import OrganizationVerificationStatus

from .models import Event, EventStatus, EventVisibility


def get_events():
    place_links = OccurrencePlace.objects.select_related("place").order_by("position", "role", "id")
    occurrences = Occurrence.objects.prefetch_related(Prefetch("place_links", queryset=place_links)).order_by("start_at", "id")
    return Event.objects.select_related(
        "activity",
        "activity__space",
        "activity__created_by",
        "category",
        "venue",
        "venue__place",
    ).prefetch_related(Prefetch("activity__occurrences", queryset=occurrences))


def _space_is_not_suspended_filter() -> Q:
    return Q(activity__space__isnull=True) | ~Q(
        activity__space__verification_status=OrganizationVerificationStatus.SUSPENDED
    )


def get_public_discoverable_events(*, upcoming_only: bool = True):
    queryset = get_events().filter(
        activity__status=EventStatus.PUBLISHED,
        activity__visibility=EventVisibility.PUBLIC,
    ).filter(_space_is_not_suspended_filter())
    if upcoming_only:
        queryset = queryset.filter(activity__occurrences__end_at__gt=timezone.now())
    return queryset.prefetch_related(
        "ticket_types__offer",
        "ticket_types__capacity_pool",
    ).distinct()


def get_events_available_for_ticket_purchase():
    return get_events().filter(
        activity__status=EventStatus.PUBLISHED,
        activity__visibility__in=[EventVisibility.PUBLIC, EventVisibility.UNLISTED],
    ).filter(_space_is_not_suspended_filter()).distinct()


def get_events_visible_to(user, *, for_detail: bool = False):
    queryset = get_events()
    public_visibilities = [EventVisibility.PUBLIC]
    if for_detail:
        public_visibilities.append(EventVisibility.UNLISTED)
    public_filter = Q(
        activity__status=EventStatus.PUBLISHED,
        activity__visibility__in=public_visibilities,
    ) & _space_is_not_suspended_filter()
    if not getattr(user, "is_authenticated", False):
        return queryset.filter(public_filter).distinct()

    activity_ids = activity_ids_with_permission(user, PermissionCode.ACTIVITY_VIEW)
    if activity_ids is None:
        return queryset
    contextual_filter = Q(activity_id__in=activity_ids) if activity_ids else Q(pk__isnull=True)
    # The original Event author keeps compatibility authority after the cutover,
    # including when the Activity is attached to an organization.
    legacy_creator_filter = Q(activity__created_by=user)
    return queryset.filter(public_filter | contextual_filter | legacy_creator_filter).distinct()


def get_manageable_events(user):
    queryset = get_events()
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    activity_ids = activity_ids_with_permission(user, PermissionCode.ACTIVITY_MANAGE)
    if activity_ids is None:
        return queryset
    contextual_filter = Q(activity_id__in=activity_ids) if activity_ids else Q(pk__isnull=True)
    legacy_creator_filter = Q(activity__created_by=user)
    return queryset.filter(contextual_filter | legacy_creator_filter).distinct()
