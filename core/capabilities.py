from authorization.constants import PermissionCode
from authorization.models import AuthorityScope
from authorization.selectors import current_mandates
from authorization.services import effective_permission_codes
from organizations.models import TeamMembership, TeamMembershipStatus


ORGANIZER_CAPABILITY_KEYS = (
    "can_manage_organization",
    "can_manage_events",
    "can_manage_finance",
    "can_manage_marketing",
    "can_manage_access",
    "can_use_access",
    "can_view_crm",
    "can_view_growth",
    "can_view_promotions",
    "can_view_loyalty",
    "can_view_partners",
    "can_view_analytics",
    "can_operate_services",
)

PLATFORM_CAPABILITY_KEYS = (
    "can_access_operations",
    "can_curate_opportunities",
    "can_view_subscription_catalog",
    "can_manage_subscription_catalog",
    "can_view_subscriptions",
    "can_manage_subscriptions",
    "can_manage_subscription_grants",
    "can_manage_subscription_reviews",
    "has_subscription_operations",
)

SERVICE_OPERATION_CODES = {
    PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL,
    PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED,
    PermissionCode.ACTIVITY_SERVICES_CONFIGURE,
}

OPPORTUNITY_CURATOR_CODES = {
    PermissionCode.OPPORTUNITIES_MANAGE,
    PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS,
    PermissionCode.OPPORTUNITIES_SOURCES_VERIFY,
    PermissionCode.OPPORTUNITIES_MERGE,
}

SUBSCRIPTION_PLATFORM_CODES = {
    PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_VIEW,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE,
}


def _empty_capabilities(*, is_staff=False, has_organization=False):
    capabilities = {"is_staff": is_staff, "has_organization": has_organization, "has_organizer_tools": False}
    capabilities.update({key: False for key in (*ORGANIZER_CAPABILITY_KEYS, *PLATFORM_CAPABILITY_KEYS)})
    return capabilities


def get_web_capabilities(user) -> dict[str, bool]:
    if not getattr(user, "is_authenticated", False):
        return _empty_capabilities()
    effective = effective_permission_codes(user)
    # Presentation of Space/Activity tools must not inherit Platform authority.
    # Platform supervision has its own capability family and server entry.
    local_codes = set(
        current_mandates()
        .filter(
            profile=user,
            scope_type__in=(AuthorityScope.SPACE, AuthorityScope.ACTIVITY),
            role__role_permissions__permission__is_active=True,
        )
        .values_list("role__role_permissions__permission__code", flat=True)
        .distinct()
    )
    has_team = TeamMembership.objects.filter(
        user=user,
        status=TeamMembershipStatus.ACTIVE,
        team__is_active=True,
    ).exists()
    can_manage_access = PermissionCode.ACCESS_MANAGE in local_codes
    can_use_access = can_manage_access or PermissionCode.ACTIVITY_ACCESS_SCAN in local_codes
    can_catalog_manage = PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE in effective
    can_subscription_manage = PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE in effective
    capabilities = {
        "is_staff": bool(user.is_staff),
        "has_organization": has_team or bool(local_codes),
        "can_manage_organization": PermissionCode.SPACE_MANAGE in local_codes,
        "can_manage_events": PermissionCode.SPACE_ACTIVITIES_MANAGE in local_codes or PermissionCode.ACTIVITY_MANAGE in local_codes,
        "can_manage_finance": PermissionCode.FINANCE_MANAGE in local_codes,
        "can_manage_marketing": PermissionCode.MARKETING_MANAGE in local_codes,
        "can_manage_access": can_manage_access,
        "can_use_access": can_use_access,
        "can_view_crm": PermissionCode.CRM_VIEW in local_codes,
        "can_view_growth": PermissionCode.ANALYTICS_GROWTH_VIEW in local_codes,
        "can_view_promotions": PermissionCode.PROMOTIONS_VIEW in local_codes,
        "can_view_loyalty": PermissionCode.LOYALTY_VIEW in local_codes,
        "can_view_partners": bool({PermissionCode.PARTNERS_MANAGE, PermissionCode.PARTNERS_FINANCE} & local_codes),
        "can_view_analytics": PermissionCode.ANALYTICS_VIEW in local_codes,
        "can_operate_services": bool(SERVICE_OPERATION_CODES & local_codes),
        "can_curate_opportunities": bool(OPPORTUNITY_CURATOR_CODES & effective),
        "can_access_operations": PermissionCode.PLATFORM_MANAGE in effective,
        "can_view_subscription_catalog": can_catalog_manage or PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_VIEW in effective,
        "can_manage_subscription_catalog": can_catalog_manage,
        "can_view_subscriptions": can_subscription_manage or PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW in effective,
        "can_manage_subscriptions": can_subscription_manage,
        "can_manage_subscription_grants": PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE in effective,
        "can_manage_subscription_reviews": PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE in effective,
        "has_subscription_operations": bool(SUBSCRIPTION_PLATFORM_CODES & effective),
    }
    capabilities["has_organizer_tools"] = any(capabilities[key] for key in ORGANIZER_CAPABILITY_KEYS)
    return capabilities
