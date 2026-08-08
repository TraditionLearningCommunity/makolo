from django.db.models import Q

from accounts.api.permissions import user_has_role
from events.models import Event
from organizations.models import OrganizationMembership

from .permissions import ANALYTICS_ROLES


def get_analytics_events(user):
    queryset = Event.objects.select_related(
        "organization",
        "organizer",
        "category",
        "venue",
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset

    organization_ids = OrganizationMembership.objects.filter(
        user=user,
        is_active=True,
        role__in=ANALYTICS_ROLES,
    ).values("organization_id")

    filters = Q(organization_id__in=organization_ids)
    if user_has_role(user, "organizer", legacy_flag="is_organizer"):
        filters |= Q(organizer=user)
    return queryset.filter(filters).distinct()
