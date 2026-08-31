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


def _user_owns_personal_activity(user, activity) -> bool:
    if activity.space_id:
        return False
    if activity.owner_profile_id:
        return activity.owner_profile_id == user.pk
    # Compatibility only for legacy rows without a canonical logical owner.
    return activity.created_by_id == user.pk


def user_can_view_activity_analytics(user, activity) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if activity.space_id:
        return can(user, PermissionCode.ANALYTICS_VIEW, activity.space)
    return _user_owns_personal_activity(user, activity)


def user_can_view_activity_financials(user, activity) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if activity.space_id:
        return can(user, PermissionCode.ANALYTICS_FINANCIALS_VIEW, activity.space)
    return _user_owns_personal_activity(user, activity)


def user_can_view_event_analytics(user, event) -> bool:
    return user_can_view_activity_analytics(user, event.activity)


def user_can_view_event_financials(user, event) -> bool:
    return user_can_view_activity_financials(user, event.activity)


def user_can_view_growth_analytics(user, organization) -> bool:
    return can(user, PermissionCode.ANALYTICS_GROWTH_VIEW, organization)


def user_can_view_growth_financials(user, organization) -> bool:
    return can(user, PermissionCode.ANALYTICS_FINANCIALS_VIEW, organization)


def user_can_manage_growth_spend(user, organization) -> bool:
    return user_can_view_growth_financials(user, organization)
