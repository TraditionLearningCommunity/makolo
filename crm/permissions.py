from organizations.models import OrganizationRole
from organizations.permissions import user_has_org_role


CRM_VIEW_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.EVENT_MANAGER,
    OrganizationRole.MARKETING,
}
CRM_MANAGE_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.MARKETING,
}


def user_can_view_crm(user, organization) -> bool:
    return user_has_org_role(user, organization, CRM_VIEW_ROLES)


def user_can_manage_crm(user, organization) -> bool:
    return user_has_org_role(user, organization, CRM_MANAGE_ROLES)
