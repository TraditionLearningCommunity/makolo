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
CUSTOMER_360_FINANCIAL_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
}


def user_can_view_crm(user, organization) -> bool:
    return user_has_org_role(user, organization, CRM_VIEW_ROLES)


def user_can_manage_crm(user, organization) -> bool:
    return user_has_org_role(user, organization, CRM_MANAGE_ROLES)


def user_can_view_customer_360_financials(user, organization) -> bool:
    """Expose les montants individuels uniquement aux propriétaires/admins.

    Marketing et Event manager conservent la vue relationnelle/engagement du
    Customer 360 sans recevoir les montants ni références financières d'un
    participant. Les comptes staff restent autorisés via user_has_org_role.
    """

    return user_has_org_role(user, organization, CUSTOMER_360_FINANCIAL_ROLES)
