from organizations.models import OrganizationMembership
from organizations.permissions import (
    ACCESS_ROLES,
    EVENT_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    MANAGE_ORGANIZATION_ROLES,
    MARKETING_ROLES,
)


def get_web_capabilities(user) -> dict[str, bool]:
    """Resolve coarse web-navigation capabilities from existing auth sources.

    This is intentionally a presentation helper, not an authorization layer.
    Views/services remain responsible for enforcing object-level permissions.
    """
    if not getattr(user, "is_authenticated", False):
        return {
            "is_staff": False,
            "has_organization": False,
            "can_manage_organization": False,
            "can_manage_events": False,
            "can_manage_finance": False,
            "can_manage_marketing": False,
            "can_manage_access": False,
            "has_organizer_tools": False,
        }

    if user.is_staff:
        return {
            "is_staff": True,
            "has_organization": True,
            "can_manage_organization": True,
            "can_manage_events": True,
            "can_manage_finance": True,
            "can_manage_marketing": True,
            "can_manage_access": True,
            "has_organizer_tools": True,
        }

    membership_roles = set(
        OrganizationMembership.objects.filter(user=user, is_active=True).values_list(
            "role", flat=True
        )
    )
    role_codes = set(
        user.roles.filter(is_active=True).values_list("code", flat=True)
    )
    legacy_organizer = "organizer" in role_codes or bool(user.is_organizer)
    scanner_agent = "scanner-agent" in role_codes or bool(user.is_scanner_agent)

    can_manage_organization = bool(membership_roles & MANAGE_ORGANIZATION_ROLES)
    can_manage_events = legacy_organizer or bool(
        membership_roles & EVENT_MANAGEMENT_ROLES
    )
    can_manage_finance = legacy_organizer or bool(membership_roles & FINANCE_ROLES)
    can_manage_marketing = legacy_organizer or bool(
        membership_roles & MARKETING_ROLES
    )
    can_manage_access = legacy_organizer or scanner_agent or bool(
        membership_roles & ACCESS_ROLES
    )
    has_organizer_tools = any(
        (
            can_manage_organization,
            can_manage_events,
            can_manage_finance,
            can_manage_marketing,
            can_manage_access,
        )
    )

    return {
        "is_staff": False,
        "has_organization": bool(membership_roles),
        "can_manage_organization": can_manage_organization,
        "can_manage_events": can_manage_events,
        "can_manage_finance": can_manage_finance,
        "can_manage_marketing": can_manage_marketing,
        "can_manage_access": can_manage_access,
        "has_organizer_tools": has_organizer_tools,
    }
