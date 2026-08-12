from django.db.models import Q

from accounts.api.permissions import user_has_role
from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from events.models import Event
from organizations.models import Organization

from .models import GrowthSpend


def get_analytics_events(user):
    queryset = Event.objects.select_related(
        "organization",
        "organizer",
        "category",
        "venue",
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    organization_ids = space_ids_with_permission(user, PermissionCode.ANALYTICS_VIEW)
    if organization_ids is None:
        return queryset

    filters = Q(organization_id__in=organization_ids)
    # Historical organization-less Event rows keep their organizer compatibility
    # until the Activity/Occurrence migration removes that path.
    if user_has_role(user, "organizer", legacy_flag="is_organizer"):
        filters |= Q(organization__isnull=True, organizer=user)
    return queryset.filter(filters).distinct()


def get_growth_organizations(user):
    queryset = Organization.objects.all().order_by("name")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    organization_ids = space_ids_with_permission(user, PermissionCode.ANALYTICS_GROWTH_VIEW)
    if organization_ids is None:
        return queryset
    return queryset.filter(pk__in=organization_ids)


def get_growth_spends(user):
    queryset = GrowthSpend.objects.select_related(
        "organization",
        "event",
        "crm_campaign",
        "partner_campaign",
        "promotion",
        "loyalty_program",
        "created_by",
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    organization_ids = space_ids_with_permission(
        user, PermissionCode.ANALYTICS_FINANCIALS_VIEW
    )
    if organization_ids is None:
        return queryset
    return queryset.filter(organization_id__in=organization_ids)
