from authorization.constants import PermissionCode
from authorization.services import can


def user_can_manage_partners(user, organization) -> bool:
    return can(user, PermissionCode.PARTNERS_MANAGE, organization)


def user_can_view_partner_finance(user, organization) -> bool:
    return can(user, PermissionCode.PARTNERS_FINANCE, organization)


def user_can_manage_partner_payouts(user, organization) -> bool:
    return can(user, PermissionCode.PARTNERS_FINANCE, organization)


def user_is_partner(user, partner) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(partner.user_id and partner.user_id == user.pk)


def user_can_view_partner(user, partner) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user_is_partner(user, partner):
        return True
    return can(user, PermissionCode.PARTNERS_MANAGE, partner.organization) or can(
        user, PermissionCode.PARTNERS_FINANCE, partner.organization
    )
