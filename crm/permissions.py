from authorization.constants import PermissionCode
from authorization.services import can


def user_can_view_crm(user, organization) -> bool:
    return can(user, PermissionCode.CRM_VIEW, organization)


def user_can_manage_crm(user, organization) -> bool:
    return can(user, PermissionCode.CRM_MANAGE, organization)


def user_can_view_customer_360_financials(user, organization) -> bool:
    """Expose individual financial details only with the explicit permission."""

    return can(user, PermissionCode.CRM_FINANCIALS_VIEW, organization)
