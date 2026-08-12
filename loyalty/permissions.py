from authorization.constants import PermissionCode
from authorization.services import can


def user_can_view_loyalty_workspace(user, organization) -> bool:
    return can(user, PermissionCode.LOYALTY_VIEW, organization)


def user_can_manage_loyalty_strategy(user, organization) -> bool:
    return can(user, PermissionCode.LOYALTY_MANAGE, organization)


def user_can_manage_loyalty_finance(user, organization) -> bool:
    return can(user, PermissionCode.LOYALTY_FINANCE, organization)
