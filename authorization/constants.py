"""Stable permission and system-role contracts for Makolo contextual authority.

Permission codes are application contracts. Rename them only through an explicit
migration and compatibility plan.
"""


class PermissionCode:
    PLATFORM_MANAGE = "platform.manage"

    SPACE_VIEW = "space.view"
    SPACE_MANAGE = "space.manage"
    SPACE_TEAM_MANAGE = "space.team.manage"
    SPACE_OWNERSHIP_MANAGE = "space.ownership.manage"

    ACTIVITY_MANAGE = "activity.manage"
    ORDERS_VIEW = "orders.view"
    TICKETS_VIEW = "tickets.view"

    FINANCE_VIEW = "finance.view"
    FINANCE_MANAGE = "finance.manage"
    MARKETING_MANAGE = "marketing.manage"
    ACCESS_MANAGE = "access.manage"

    CRM_VIEW = "crm.view"
    CRM_MANAGE = "crm.manage"
    CRM_FINANCIALS_VIEW = "crm.financials.view"

    PROMOTIONS_VIEW = "promotions.view"
    PROMOTIONS_MANAGE = "promotions.manage"
    PROMOTIONS_FINANCIALS_VIEW = "promotions.financials.view"

    LOYALTY_VIEW = "loyalty.view"
    LOYALTY_MANAGE = "loyalty.manage"
    LOYALTY_FINANCE = "loyalty.finance"

    PARTNERS_MANAGE = "partners.manage"
    PARTNERS_FINANCE = "partners.finance"

    ANALYTICS_VIEW = "analytics.view"
    ANALYTICS_GROWTH_VIEW = "analytics.growth.view"
    ANALYTICS_FINANCIALS_VIEW = "analytics.financials.view"
    GROWTH_FEEDBACK_VIEW = "growth.feedback.view"


class SystemRoleCode:
    PLATFORM_ADMIN = "makolo-platform-admin"
    SPACE_OWNER = "space-owner"
    SPACE_ADMIN = "space-admin"
    ACTIVITY_MANAGER = "activity-manager"
    FINANCE = "finance"
    MARKETING = "marketing"
    ACCESS_MANAGER = "access-manager"


SPACE_PERMISSION_CODES = {
    value
    for name, value in PermissionCode.__dict__.items()
    if name.isupper() and value != PermissionCode.PLATFORM_MANAGE
}

STANDARD_SPACE_ROLE_CODES = {
    SystemRoleCode.SPACE_OWNER,
    SystemRoleCode.SPACE_ADMIN,
    SystemRoleCode.ACTIVITY_MANAGER,
    SystemRoleCode.FINANCE,
    SystemRoleCode.MARKETING,
    SystemRoleCode.ACCESS_MANAGER,
}

LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE = {
    "owner": SystemRoleCode.SPACE_OWNER,
    "admin": SystemRoleCode.SPACE_ADMIN,
    "event_manager": SystemRoleCode.ACTIVITY_MANAGER,
    "finance": SystemRoleCode.FINANCE,
    "marketing": SystemRoleCode.MARKETING,
    "scanner_manager": SystemRoleCode.ACCESS_MANAGER,
}

SYSTEM_ROLE_TO_LEGACY_ORGANIZATION_ROLE = {
    value: key for key, value in LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE.items()
}
