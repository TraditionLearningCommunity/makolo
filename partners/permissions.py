from organizations.permissions import (
    FINANCE_ROLES,
    MARKETING_ROLES,
    MANAGE_ORGANIZATION_ROLES,
    get_membership,
    user_has_org_role,
)


PARTNER_MANAGEMENT_ROLES = MANAGE_ORGANIZATION_ROLES | MARKETING_ROLES
PARTNER_FINANCE_ROLES = MANAGE_ORGANIZATION_ROLES | FINANCE_ROLES


def user_can_manage_partners(user, organization) -> bool:
    return user_has_org_role(user, organization, PARTNER_MANAGEMENT_ROLES)


def user_can_view_partner_finance(user, organization) -> bool:
    return user_has_org_role(user, organization, PARTNER_FINANCE_ROLES)


def user_can_manage_partner_payouts(user, organization) -> bool:
    return user_has_org_role(user, organization, PARTNER_FINANCE_ROLES)


def user_is_partner(user, partner) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    return bool(partner.user_id and partner.user_id == user.pk)


def user_can_view_partner(user, partner) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    if user_is_partner(user, partner):
        return True
    membership = get_membership(user, partner.organization)
    return bool(membership and membership.role in PARTNER_MANAGEMENT_ROLES | PARTNER_FINANCE_ROLES)
