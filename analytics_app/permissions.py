from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import OrganizationRole


# Deprecated compatibility exports used by older tests/callers for vocabulary.
# They are not consulted by Task 9 authorization decisions.
ANALYTICS_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.EVENT_MANAGER,
    OrganizationRole.FINANCE,
    OrganizationRole.MARKETING,
    OrganizationRole.SCANNER_MANAGER,
}
GROWTH_ANALYTICS_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.EVENT_MANAGER,
    OrganizationRole.FINANCE,
    OrganizationRole.MARKETING,
}


def user_can_view_event_analytics(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if event.activity.space_id:
        return can(user, PermissionCode.ANALYTICS_VIEW, event.activity.space)
    # Historical personal Activity compatibility only; no Event role grants it.
    return event.activity.created_by_id == user.pk


def user_can_view_event_financials(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if event.activity.space_id:
        return can(user, PermissionCode.ANALYTICS_FINANCIALS_VIEW, event.activity.space)
    return event.activity.created_by_id == user.pk


def user_can_view_growth_analytics(user, organization) -> bool:
    return can(user, PermissionCode.ANALYTICS_GROWTH_VIEW, organization)


def user_can_view_growth_financials(user, organization) -> bool:
    return can(user, PermissionCode.ANALYTICS_FINANCIALS_VIEW, organization)


def user_can_manage_growth_spend(user, organization) -> bool:
    return user_can_view_growth_financials(user, organization)
