from django.db.models import Q

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
        & (
            Q(organization__isnull=True)
            | ~Q(
                organization__verification_status=(
                    OrganizationVerificationStatus.SUSPENDED
                )
            )
        )
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
