from authorization.constants import PermissionCode
from authorization.services import can, space_ids_with_permission
from organizations.models import Organization, OrganizationRole


# Deprecated compatibility exports. They describe the historical mapping only;
# authorization decisions below no longer read OrganizationMembership.role.
GROWTH_VIEW_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.EVENT_MANAGER,
    OrganizationRole.FINANCE,
    OrganizationRole.MARKETING,
}
GROWTH_MANAGE_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.MARKETING,
}
GROWTH_FEEDBACK_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.EVENT_MANAGER,
    OrganizationRole.MARKETING,
}


def user_can_view_growth_v1(user, organization) -> bool:
    return can(user, PermissionCode.ANALYTICS_GROWTH_VIEW, organization)


def user_can_manage_growth_acquisition(user, organization) -> bool:
    return can(user, PermissionCode.MARKETING_MANAGE, organization)


def user_can_view_growth_financials(user, organization) -> bool:
    return can(user, PermissionCode.ANALYTICS_FINANCIALS_VIEW, organization)


def user_can_view_private_feedback(user, organization) -> bool:
    return can(user, PermissionCode.GROWTH_FEEDBACK_VIEW, organization)


def get_growth_organizations(user):
    queryset = Organization.objects.all().order_by("name")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    space_ids = space_ids_with_permission(user, PermissionCode.ANALYTICS_GROWTH_VIEW)
    if space_ids is None:
        return queryset
    return queryset.filter(pk__in=space_ids)
