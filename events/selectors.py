from django.db.models import Q
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, space_ids_with_permission
from organizations.models import OrganizationVerificationStatus

from .models import Event, EventStatus, EventVisibility


def get_events():
    return Event.objects.select_related("organizer", "organization", "activity", "category", "venue", "venue__place")


def _organization_is_not_suspended_filter() -> Q:
    return Q(organization__isnull=True) | ~Q(organization__verification_status=OrganizationVerificationStatus.SUSPENDED)


def get_public_discoverable_events(*, upcoming_only: bool = True):
    queryset = get_events().filter(status=EventStatus.PUBLISHED, visibility=EventVisibility.PUBLIC).filter(_organization_is_not_suspended_filter())
    if upcoming_only:
        queryset = queryset.filter(end_at__gt=timezone.now())
    return queryset.prefetch_related("ticket_types")


def get_events_available_for_ticket_purchase():
    return get_events().filter(status=EventStatus.PUBLISHED, visibility__in=[EventVisibility.PUBLIC, EventVisibility.UNLISTED]).filter(_organization_is_not_suspended_filter())


def _legacy_space_filter(user, permission_code):
    space_ids = space_ids_with_permission(user, permission_code)
    if space_ids is None:
        return None
    if not space_ids:
        return Q(pk__isnull=True)
    return Q(activity__isnull=True, organization_id__in=space_ids)


def get_events_visible_to(user, *, for_detail: bool = False):
    queryset = get_events()
    public_visibilities = [EventVisibility.PUBLIC]
    if for_detail:
        public_visibilities.append(EventVisibility.UNLISTED)
    public_filter = Q(status=EventStatus.PUBLISHED, visibility__in=public_visibilities) & _organization_is_not_suspended_filter()
    if not getattr(user, "is_authenticated", False):
        return queryset.filter(public_filter)
    activity_ids = activity_ids_with_permission(user, PermissionCode.ACTIVITY_VIEW)
    if activity_ids is None:
        return queryset
    contextual_filter = Q(activity_id__in=activity_ids) if activity_ids else Q(pk__isnull=True)
    legacy_space_filter = _legacy_space_filter(user, PermissionCode.SPACE_ACTIVITIES_VIEW)
    if legacy_space_filter is None:
        return queryset
    return queryset.filter(public_filter | Q(organizer=user) | contextual_filter | legacy_space_filter).distinct()


def get_manageable_events(user):
    queryset = get_events()
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    activity_ids = activity_ids_with_permission(user, PermissionCode.ACTIVITY_MANAGE)
    if activity_ids is None:
        return queryset
    contextual_filter = Q(activity_id__in=activity_ids) if activity_ids else Q(pk__isnull=True)
    legacy_space_filter = _legacy_space_filter(user, PermissionCode.SPACE_ACTIVITIES_MANAGE)
    if legacy_space_filter is None:
        return queryset
    legacy_personal_filter = Q(activity__isnull=True, organization__isnull=True, organizer=user)
    return queryset.filter(contextual_filter | legacy_space_filter | legacy_personal_filter).distinct()
