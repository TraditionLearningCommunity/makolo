from django.db.models import Q

from .models import Event, EventStatus, EventVisibility


def get_events():
    return Event.objects.select_related(
        "organizer",
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

    public_filter = Q(
        status=EventStatus.PUBLISHED,
        visibility__in=public_visibilities,
    )

    if user.is_authenticated:
        return queryset.filter(public_filter | Q(organizer=user)).distinct()

    return queryset.filter(public_filter)


def get_manageable_events(user):
    queryset = get_events()
    if user.is_staff:
        return queryset
    return queryset.filter(organizer=user)
