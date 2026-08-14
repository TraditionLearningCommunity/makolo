"""Stable permission and system-role contracts for Makolo contextual authority."""


class PermissionCode:
    PLATFORM_MANAGE = "platform.manage"
    SPACE_VIEW = "space.view"
    SPACE_MANAGE = "space.manage"
    SPACE_TEAM_MANAGE = "space.team.manage"
    SPACE_OWNERSHIP_MANAGE = "space.ownership.manage"
    SPACE_GROUPS_VIEW = "space.groups.view"
    SPACE_GROUPS_MANAGE = "space.groups.manage"
    SPACE_PLACES_VIEW = "space.places.view"
    SPACE_PLACES_MANAGE = "space.places.manage"
    SPACE_ACTIVITIES_VIEW = "space.activities.view"
    SPACE_ACTIVITIES_MANAGE = "space.activities.manage"
    GROUP_VIEW = "group.view"
    GROUP_MANAGE = "group.manage"
    GROUP_MEMBERS_VIEW = "group.members.view"
    GROUP_MEMBERS_MANAGE = "group.members.manage"
    GROUP_INVITATIONS_MANAGE = "group.invitations.manage"
    GROUP_SNAPSHOTS_CREATE = "group.snapshots.create"
    GROUP_OWNERSHIP_MANAGE = "group.ownership.manage"
    ACTIVITY_VIEW = "activity.view"
    ACTIVITY_MANAGE = "activity.manage"
    ACTIVITY_REQUESTS_VIEW = "activity.requests.view"
    ACTIVITY_REQUESTS_DECIDE = "activity.requests.decide"
    ACTIVITY_ACCESS_VIEW = "activity.access.view"
    ACTIVITY_ACCESS_MANAGE = "activity.access.manage"
    ACTIVITY_COMMERCE_VIEW = "activity.commerce.view"
    ACTIVITY_COMMERCE_MANAGE = "activity.commerce.manage"
    ACTIVITY_CAPACITY_VIEW = "activity.capacity.view"
    ACTIVITY_CAPACITY_MANAGE = "activity.capacity.manage"
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
    # Historical Python contract kept as the Space-scoped Activity portfolio role.
    ACTIVITY_MANAGER = "space-activity-manager"
    SPACE_ACTIVITY_MANAGER = ACTIVITY_MANAGER
    # New local role introduced with AuthorityScope.ACTIVITY.
    ACTIVITY_LOCAL_MANAGER = "activity-manager"
    FINANCE = "finance"
    MARKETING = "marketing"
    ACCESS_MANAGER = "access-manager"
    GROUP_OWNER = "group-owner"
    GROUP_ADMIN = "group-admin"
    GROUP_MODERATOR = "group-moderator"


GROUP_PERMISSION_CODES = {
    PermissionCode.GROUP_VIEW,
    PermissionCode.GROUP_MANAGE,
    PermissionCode.GROUP_MEMBERS_VIEW,
    PermissionCode.GROUP_MEMBERS_MANAGE,
    PermissionCode.GROUP_INVITATIONS_MANAGE,
    PermissionCode.GROUP_SNAPSHOTS_CREATE,
    PermissionCode.GROUP_OWNERSHIP_MANAGE,
}
ACTIVITY_PERMISSION_CODES = {
    PermissionCode.ACTIVITY_VIEW,
    PermissionCode.ACTIVITY_MANAGE,
    PermissionCode.ACTIVITY_REQUESTS_VIEW,
    PermissionCode.ACTIVITY_REQUESTS_DECIDE,
    PermissionCode.ACTIVITY_ACCESS_VIEW,
    PermissionCode.ACTIVITY_ACCESS_MANAGE,
    PermissionCode.ACTIVITY_COMMERCE_VIEW,
    PermissionCode.ACTIVITY_COMMERCE_MANAGE,
    PermissionCode.ACTIVITY_CAPACITY_VIEW,
    PermissionCode.ACTIVITY_CAPACITY_MANAGE,
}
SPACE_PERMISSION_CODES = {
    value
    for name, value in PermissionCode.__dict__.items()
    if name.isupper()
    and value != PermissionCode.PLATFORM_MANAGE
    and value not in GROUP_PERMISSION_CODES
    and value not in ACTIVITY_PERMISSION_CODES
}

STANDARD_SPACE_ROLE_CODES = {
    SystemRoleCode.SPACE_OWNER,
    SystemRoleCode.SPACE_ADMIN,
    SystemRoleCode.ACTIVITY_MANAGER,
    SystemRoleCode.FINANCE,
    SystemRoleCode.MARKETING,
    SystemRoleCode.ACCESS_MANAGER,
}
STANDARD_GROUP_ROLE_CODES = {
    SystemRoleCode.GROUP_OWNER,
    SystemRoleCode.GROUP_ADMIN,
    SystemRoleCode.GROUP_MODERATOR,
}
STANDARD_ACTIVITY_ROLE_CODES = {SystemRoleCode.ACTIVITY_LOCAL_MANAGER}

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
