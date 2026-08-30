from django.db.models import Q
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import effective_permission_codes
from organizations.models import TeamMembership, TeamMembershipStatus
from scanner.models import ScannerAssignment


CAPABILITY_KEYS = (
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
    "can_curate_opportunities",
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


def _empty_capabilities(*, is_staff=False, has_organization=False):
    capabilities = {"is_staff": is_staff, "has_organization": has_organization, "has_organizer_tools": False}
    capabilities.update({key: False for key in CAPABILITY_KEYS})
    return capabilities


def _has_current_scanner_assignment(user) -> bool:
    now = timezone.now()
    return ScannerAssignment.objects.filter(agent=user, is_active=True).filter(Q(valid_from__isnull=True) | Q(valid_from__lte=now)).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now)).exists()


def get_web_capabilities(user) -> dict[str, bool]:
    if not getattr(user, "is_authenticated", False):
        return _empty_capabilities()
    effective = effective_permission_codes(user)
    has_team = TeamMembership.objects.filter(user=user, status=TeamMembershipStatus.ACTIVE, team__is_active=True).exists()
    can_manage_access = PermissionCode.ACCESS_MANAGE in effective
    can_use_access = can_manage_access or _has_current_scanner_assignment(user)
    capabilities = {
        "is_staff": bool(user.is_staff),
        "has_organization": has_team or PermissionCode.SPACE_VIEW in effective,
        "can_manage_organization": PermissionCode.SPACE_MANAGE in effective,
        "can_manage_events": PermissionCode.SPACE_ACTIVITIES_MANAGE in effective or PermissionCode.ACTIVITY_MANAGE in effective,
        "can_manage_finance": PermissionCode.FINANCE_MANAGE in effective,
        "can_manage_marketing": PermissionCode.MARKETING_MANAGE in effective,
        "can_manage_access": can_manage_access,
        "can_use_access": can_use_access,
        "can_view_crm": PermissionCode.CRM_VIEW in effective,
        "can_view_growth": PermissionCode.ANALYTICS_GROWTH_VIEW in effective,
        "can_view_promotions": PermissionCode.PROMOTIONS_VIEW in effective,
        "can_view_loyalty": PermissionCode.LOYALTY_VIEW in effective,
        "can_view_partners": bool({PermissionCode.PARTNERS_MANAGE, PermissionCode.PARTNERS_FINANCE} & effective),
        "can_view_analytics": PermissionCode.ANALYTICS_VIEW in effective,
        "can_operate_services": bool(SERVICE_OPERATION_CODES & effective),
        "can_curate_opportunities": bool(OPPORTUNITY_CURATOR_CODES & effective),
    }
    capabilities["has_organizer_tools"] = any(capabilities[key] for key in CAPABILITY_KEYS)
    return capabilities