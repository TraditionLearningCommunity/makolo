from organizations.permissions import FINANCE_ROLES, MARKETING_ROLES, user_has_org_role


LOYALTY_VIEW_ROLES = set(MARKETING_ROLES) | set(FINANCE_ROLES)


def user_can_view_loyalty_workspace(user, organization) -> bool:
    return user_has_org_role(user, organization, LOYALTY_VIEW_ROLES)


def user_can_manage_loyalty_strategy(user, organization) -> bool:
    return user_has_org_role(user, organization, MARKETING_ROLES)


def user_can_manage_loyalty_finance(user, organization) -> bool:
    return user_has_org_role(user, organization, FINANCE_ROLES)
