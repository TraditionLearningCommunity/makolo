from django.db.models import Q

from organizations.models import Organization
from organizations.permissions import (
    EVENT_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    MARKETING_ROLES,
    user_has_org_role,
)


GROWTH_VIEW_ROLES = set(EVENT_MANAGEMENT_ROLES) | set(MARKETING_ROLES) | set(FINANCE_ROLES)
GROWTH_MANAGE_ROLES = set(MARKETING_ROLES)
GROWTH_FEEDBACK_ROLES = set(EVENT_MANAGEMENT_ROLES) | set(MARKETING_ROLES)


def user_can_view_growth_v1(user, organization) -> bool:
    return user_has_org_role(user, organization, GROWTH_VIEW_ROLES)


def user_can_manage_growth_acquisition(user, organization) -> bool:
    return user_has_org_role(user, organization, GROWTH_MANAGE_ROLES)


def user_can_view_growth_financials(user, organization) -> bool:
    return user_has_org_role(user, organization, FINANCE_ROLES)


def user_can_view_private_feedback(user, organization) -> bool:
    return user_has_org_role(user, organization, GROWTH_FEEDBACK_ROLES)


def get_growth_organizations(user):
    queryset = Organization.objects.all().order_by("name")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    return queryset.filter(
        memberships__user=user,
        memberships__is_active=True,
        memberships__role__in=GROWTH_VIEW_ROLES,
    ).distinct()
