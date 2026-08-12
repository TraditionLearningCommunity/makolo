from authorization.constants import PermissionCode
from authorization.services import can


def user_can_view_promotions(user, organization) -> bool:
    return can(user, PermissionCode.PROMOTIONS_VIEW, organization)


def user_can_manage_promotions(user, organization) -> bool:
    return can(user, PermissionCode.PROMOTIONS_MANAGE, organization)


def user_can_view_promotion_financials(user, organization) -> bool:
    return can(user, PermissionCode.PROMOTIONS_FINANCIALS_VIEW, organization)
