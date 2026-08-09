from django.db.models import Q

from accounts.api.permissions import user_has_role
from events.models import Event
from organizations.models import Organization, OrganizationMembership
from organizations.permissions import FINANCE_ROLES

from .models import GrowthSpend
from .permissions import ANALYTICS_ROLES, GROWTH_ANALYTICS_ROLES


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


def get_growth_organizations(user):
    queryset = Organization.objects.all().order_by("name")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    return queryset.filter(
        memberships__user=user,
        memberships__is_active=True,
        memberships__role__in=GROWTH_ANALYTICS_ROLES,
    ).distinct()


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
    if user.is_staff:
        return queryset
    finance_org_ids = OrganizationMembership.objects.filter(
        user=user,
        is_active=True,
        role__in=FINANCE_ROLES,
    ).values("organization_id")
    return queryset.filter(organization_id__in=finance_org_ids)
