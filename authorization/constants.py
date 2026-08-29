"""Stable permission and system-role contracts for Makolo contextual authority."""


class PermissionCode:
    PLATFORM_MANAGE = "platform.manage"
    OPPORTUNITIES_MANAGE = "opportunities.manage"
    OPPORTUNITIES_REVIEW_SUBMISSIONS = "opportunities.review_submissions"
    OPPORTUNITIES_SOURCES_VERIFY = "opportunities.sources.verify"
    OPPORTUNITIES_MERGE = "opportunities.merge"
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
    ACTIVITY_ACCESS_SCAN = "activity.access.scan"
    ACTIVITY_OPERATIONS_VIEW = "activity.operations.view"
    ACTIVITY_OPERATIONS_MANAGE = "activity.operations.manage"
    ACTIVITY_COMMERCE_VIEW = "activity.commerce.view"
    ACTIVITY_COMMERCE_MANAGE = "activity.commerce.manage"
    ACTIVITY_CAPACITY_VIEW = "activity.capacity.view"
    ACTIVITY_CAPACITY_MANAGE = "activity.capacity.manage"
    ACTIVITY_FINANCE_VIEW = "activity.finance.view"
    ACTIVITY_FINANCE_MANAGE = "activity.finance.manage"
    ACTIVITY_SERVICES_CONFIGURE = "activity.services.configure"
    ACTIVITY_SERVICES_CASES_VIEW_ALL = "activity.services.cases.view_all"
    ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED = "activity.services.cases.view_assigned"
    ACTIVITY_SERVICES_CASES_MANAGE = "activity.services.cases.manage"
    ACTIVITY_SERVICES_ASSIGNMENTS_MANAGE = "activity.services.assignments.manage"
    ACTIVITY_SERVICES_STEPS_MANAGE = "activity.services.steps.manage"
    ACTIVITY_SERVICES_BLOCKERS_MANAGE = "activity.services.blockers.manage"
    ACTIVITY_SERVICES_ARTIFACTS_VIEW = "activity.services.artifacts.view"
    ACTIVITY_SERVICES_ARTIFACTS_MANAGE = "activity.services.artifacts.manage"
    ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW = "activity.services.artifacts.restricted_view"
    ACTIVITY_SERVICES_REVIEWS_MANAGE = "activity.services.reviews.manage"
    ACTIVITY_SERVICES_NOTES_INTERNAL = "activity.services.notes.internal"
    ACTIVITY_SERVICES_OUTCOMES_MANAGE = "activity.services.outcomes.manage"
    ACTIVITY_SERVICES_PAYMENT_EVIDENCE_VERIFY = "activity.services.payment_evidence.verify"
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
    OPPORTUNITY_CURATOR = "opportunity-curator"
    SPACE_OWNER = "space-owner"
    SPACE_ADMIN = "space-admin"
    # Historical Python contract kept as the Space-scoped Activity portfolio role.
    ACTIVITY_MANAGER = "space-activity-manager"
    SPACE_ACTIVITY_MANAGER = ACTIVITY_MANAGER
    # Local Activity-scoped roles.
    ACTIVITY_LOCAL_MANAGER = "activity-manager"
    ACTIVITY_SCANNER = "activity-scanner"
    ACTIVITY_OPERATIONS_MANAGER = "activity-operations-manager"
    ACTIVITY_FINANCE = "activity-finance"
    ACTIVITY_SERVICE_MANAGER = "activity-service-manager"
    ACTIVITY_SERVICE_FACILITATOR = "activity-service-facilitator"
    ACTIVITY_SERVICE_REVIEWER = "activity-service-reviewer"
    FINANCE = "finance"
    MARKETING = "marketing"
    ACCESS_MANAGER = "access-manager"
    GROUP_OWNER = "group-owner"
    GROUP_ADMIN = "group-admin"
    GROUP_MODERATOR = "group-moderator"


PLATFORM_PERMISSION_CODES = {
    PermissionCode.PLATFORM_MANAGE,
    PermissionCode.OPPORTUNITIES_MANAGE,
    PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS,
    PermissionCode.OPPORTUNITIES_SOURCES_VERIFY,
    PermissionCode.OPPORTUNITIES_MERGE,
}
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
    PermissionCode.ACTIVITY_ACCESS_SCAN,
    PermissionCode.ACTIVITY_OPERATIONS_VIEW,
    PermissionCode.ACTIVITY_OPERATIONS_MANAGE,
    PermissionCode.ACTIVITY_COMMERCE_VIEW,
    PermissionCode.ACTIVITY_COMMERCE_MANAGE,
    PermissionCode.ACTIVITY_CAPACITY_VIEW,
    PermissionCode.ACTIVITY_CAPACITY_MANAGE,
    PermissionCode.ACTIVITY_FINANCE_VIEW,
    PermissionCode.ACTIVITY_FINANCE_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_CONFIGURE,
    PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL,
    PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED,
    PermissionCode.ACTIVITY_SERVICES_CASES_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_ASSIGNMENTS_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_STEPS_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_BLOCKERS_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW,
    PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW,
    PermissionCode.ACTIVITY_SERVICES_REVIEWS_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_NOTES_INTERNAL,
    PermissionCode.ACTIVITY_SERVICES_OUTCOMES_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_PAYMENT_EVIDENCE_VERIFY,
}
SPACE_PERMISSION_CODES = {
    value
    for name, value in PermissionCode.__dict__.items()
    if name.isupper()
    and value not in PLATFORM_PERMISSION_CODES
    and value not in GROUP_PERMISSION_CODES
    and value not in ACTIVITY_PERMISSION_CODES
}

STANDARD_PLATFORM_ROLE_CODES = {
    SystemRoleCode.PLATFORM_ADMIN,
    SystemRoleCode.OPPORTUNITY_CURATOR,
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
STANDARD_ACTIVITY_ROLE_CODES = {
    SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
    SystemRoleCode.ACTIVITY_SCANNER,
    SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
    SystemRoleCode.ACTIVITY_FINANCE,
    SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
    SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR,
    SystemRoleCode.ACTIVITY_SERVICE_REVIEWER,
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
