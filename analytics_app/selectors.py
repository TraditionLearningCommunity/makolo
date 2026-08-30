from django.db.models import Q

from activities.models import Activity
from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from events.models import Event
from organizations.models import Organization

from .models import GrowthSpend


def get_analytics_activities(user):
    queryset = Activity.objects.select_related("space", "owner_profile", "created_by").prefetch_related("occurrences")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    space_ids = space_ids_with_permission(user, PermissionCode.ANALYTICS_VIEW)
    if space_ids is None:
        return queryset

    filters = Q(space_id__in=space_ids) | Q(space__isnull=True, owner_profile=user)
    # Compatibility only for legacy personal Activities created before the
    # canonical owner_profile contract could be populated safely.
    filters |= Q(space__isnull=True, owner_profile__isnull=True, created_by=user)
    return queryset.filter(filters).distinct()


def get_service_analytics_activities(user):
    return get_analytics_activities(user).filter(service_details__isnull=False).distinct()


def get_analytics_events(user):
    queryset = Event.objects.select_related(
        "activity",
        "activity__space",
        "activity__owner_profile",
        "activity__created_by",
        "category",
        "venue",
        "venue__place",
    ).prefetch_related("activity__occurrences")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    space_ids = space_ids_with_permission(user, PermissionCode.ANALYTICS_VIEW)
    if space_ids is None:
        return queryset

    filters = Q(activity__space_id__in=space_ids)
    # Compatibility for historical personal Activities only. Authority still
    # comes from the canonical Activity owner, never an Event role.
    filters |= Q(activity__space__isnull=True, activity__owner_profile=user)
    filters |= Q(
        activity__space__isnull=True,
        activity__owner_profile__isnull=True,
        activity__created_by=user,
    )
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
        "organization", "event", "crm_campaign", "partner_campaign", "promotion",
        "loyalty_program", "created_by",
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    organization_ids = space_ids_with_permission(user, PermissionCode.ANALYTICS_FINANCIALS_VIEW)
    if organization_ids is None:
        return queryset
    return queryset.filter(organization_id__in=organization_ids)
