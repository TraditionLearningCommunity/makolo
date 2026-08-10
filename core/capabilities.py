from analytics_app.permissions import ANALYTICS_ROLES
from crm.permissions import CRM_VIEW_ROLES
from growth.permissions import GROWTH_VIEW_ROLES
from loyalty.permissions import LOYALTY_VIEW_ROLES
from partners.permissions import PARTNER_FINANCE_ROLES, PARTNER_MANAGEMENT_ROLES
from promotions.permissions import PROMOTION_VIEW_ROLES
from organizations.models import OrganizationMembership
from organizations.permissions import (
    ACCESS_ROLES,
    EVENT_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    MANAGE_ORGANIZATION_ROLES,
    MARKETING_ROLES,
)


CAPABILITY_KEYS = (
    "can_manage_organization",
    "can_manage_events",
    "can_manage_finance",
    "can_manage_marketing",
    "can_manage_access",
    "can_view_crm",
    "can_view_growth",
    "can_view_promotions",
    "can_view_loyalty",
    "can_view_partners",
    "can_view_analytics",
)


def _empty_capabilities(*, is_staff=False, has_organization=False):
    capabilities = {
        "is_staff": is_staff,
        "has_organization": has_organization,
        "has_organizer_tools": is_staff,
    }
    capabilities.update({key: is_staff for key in CAPABILITY_KEYS})
    return capabilities


def get_web_capabilities(user) -> dict[str, bool]:
    """Resolve presentation capabilities from existing authorization role sets.

    This intentionally does not authorize requests. It mirrors the role sets
    already used by each domain so templates can avoid advertising tools the
    user cannot use; object-level checks in views/services remain authoritative.
    """
    if not getattr(user, "is_authenticated", False):
        return _empty_capabilities()
    if user.is_staff:
        return _empty_capabilities(is_staff=True, has_organization=True)

    membership_roles = set(
        OrganizationMembership.objects.filter(user=user, is_active=True).values_list(
            "role", flat=True
        )
    )
    role_codes = set(user.roles.filter(is_active=True).values_list("code", flat=True))
    legacy_organizer = "organizer" in role_codes or bool(user.is_organizer)
    scanner_agent = (
        "scanner-agent" in role_codes
        or "scanner" in role_codes
        or bool(user.is_scanner_agent)
    )

    capabilities = {
        "is_staff": False,
        "has_organization": bool(membership_roles),
        "can_manage_organization": legacy_organizer
        or bool(membership_roles & MANAGE_ORGANIZATION_ROLES),
        "can_manage_events": legacy_organizer
        or bool(membership_roles & EVENT_MANAGEMENT_ROLES),
        "can_manage_finance": legacy_organizer
        or bool(membership_roles & FINANCE_ROLES),
        "can_manage_marketing": legacy_organizer
        or bool(membership_roles & MARKETING_ROLES),
        "can_manage_access": legacy_organizer
        or scanner_agent
        or bool(membership_roles & ACCESS_ROLES),
        "can_view_crm": legacy_organizer or bool(membership_roles & CRM_VIEW_ROLES),
        "can_view_growth": legacy_organizer
        or bool(membership_roles & GROWTH_VIEW_ROLES),
        "can_view_promotions": legacy_organizer
        or bool(membership_roles & PROMOTION_VIEW_ROLES),
        "can_view_loyalty": legacy_organizer
        or bool(membership_roles & LOYALTY_VIEW_ROLES),
        "can_view_partners": legacy_organizer
        or bool(
            membership_roles
            & (set(PARTNER_MANAGEMENT_ROLES) | set(PARTNER_FINANCE_ROLES))
        ),
        "can_view_analytics": legacy_organizer
        or bool(membership_roles & ANALYTICS_ROLES),
    }
    capabilities["has_organizer_tools"] = any(
        capabilities[key] for key in CAPABILITY_KEYS
    )
    return capabilities
