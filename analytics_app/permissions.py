from accounts.api.permissions import user_has_role
from organizations.models import OrganizationRole
from organizations.permissions import FINANCE_ROLES, user_has_org_role


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
    if user.is_staff:
        return True
    if event.organization_id:
        return user_has_org_role(user, event.organization, ANALYTICS_ROLES)
    return event.organizer_id == user.pk and user_has_role(
        user,
        "organizer",
        legacy_flag="is_organizer",
    )


def user_can_view_event_financials(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    if event.organization_id:
        return user_has_org_role(user, event.organization, FINANCE_ROLES)
    return event.organizer_id == user.pk and user_has_role(
        user,
        "organizer",
        legacy_flag="is_organizer",
    )


def user_can_view_growth_analytics(user, organization) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    return user_has_org_role(user, organization, GROWTH_ANALYTICS_ROLES)


def user_can_view_growth_financials(user, organization) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    return user_has_org_role(user, organization, FINANCE_ROLES)


def user_can_manage_growth_spend(user, organization) -> bool:
    return user_can_view_growth_financials(user, organization)
