from organizations.models import OrganizationRole
from organizations.permissions import user_has_org_role


PROMOTION_VIEW_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.EVENT_MANAGER,
    OrganizationRole.FINANCE,
    OrganizationRole.MARKETING,
}
PROMOTION_MANAGE_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.MARKETING,
}
PROMOTION_FINANCE_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.FINANCE,
}


def user_can_view_promotions(user, organization) -> bool:
    return user_has_org_role(user, organization, PROMOTION_VIEW_ROLES)


def user_can_manage_promotions(user, organization) -> bool:
    return user_has_org_role(user, organization, PROMOTION_MANAGE_ROLES)


def user_can_view_promotion_financials(user, organization) -> bool:
    return user_has_org_role(user, organization, PROMOTION_FINANCE_ROLES)
