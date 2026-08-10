from django.db.models import Q
from django.utils import timezone

from organizations.models import (
    OrganizationRole,
    OrganizationVerificationStatus,
)

from .models import Event, EventStatus, EventVisibility


MANAGER_ROLES = [
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.EVENT_MANAGER,
]


def get_events():
    return Event.objects.select_related(
        "organizer",
        "organization",
        "category",
        "venue",
    )


def _organization_is_not_suspended_filter() -> Q:
    return Q(organization__isnull=True) | ~Q(
        organization__verification_status=OrganizationVerificationStatus.SUSPENDED
    )


def get_public_discoverable_events(*, upcoming_only: bool = True):
    """Participant-facing public event read model.

    This selector never includes events merely because the current user can
    administer them. It is safe to use for public/mobile discovery.
    """
    queryset = get_events().filter(
        status=EventStatus.PUBLISHED,
        visibility=EventVisibility.PUBLIC,
    ).filter(_organization_is_not_suspended_filter())
    if upcoming_only:
        queryset = queryset.filter(end_at__gt=timezone.now())
    return queryset.prefetch_related("ticket_types")


def get_events_available_for_ticket_purchase():
    """Events a participant may purchase from, including direct unlisted links."""
    return get_events().filter(
        status=EventStatus.PUBLISHED,
        visibility__in=[EventVisibility.PUBLIC, EventVisibility.UNLISTED],
    ).filter(_organization_is_not_suspended_filter())


def get_events_visible_to(user, *, for_detail: bool = False):
    queryset = get_events()
    if user.is_authenticated and user.is_staff:
        return queryset

    public_visibilities = [EventVisibility.PUBLIC]
    if for_detail:
        public_visibilities.append(EventVisibility.UNLISTED)

    public_filter = (
        Q(
            status=EventStatus.PUBLISHED,
            visibility__in=public_visibilities,
        )
        & _organization_is_not_suspended_filter()
    )

    if user.is_authenticated:
        member_filter = Q(
            organization__memberships__user=user,
            organization__memberships__is_active=True,
        )
        return queryset.filter(
            public_filter | Q(organizer=user) | member_filter
        ).distinct()
    return queryset.filter(public_filter)


def get_manageable_events(user):
    queryset = get_events()
    if user.is_staff:
        return queryset
    return queryset.filter(
        Q(organizer=user)
        | Q(
            organization__memberships__user=user,
            organization__memberships__is_active=True,
            organization__memberships__role__in=MANAGER_ROLES,
        )
    ).distinct()
