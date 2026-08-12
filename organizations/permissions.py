from django.db.models import Q
from django.utils import timezone

from authorization.constants import (
    LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE,
    PermissionCode,
)
from authorization.models import AuthorityScope, Mandate, MandateStatus
from authorization.services import can, has_platform_authority

from .models import (
    OrganizationMembership,
    OrganizationRole,
    OrganizationVerificationStatus,
)


# Compatibility constants for callers that have not yet moved from the old role
# vocabulary. They are no longer an authority source.
MANAGE_ORGANIZATION_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
}
EVENT_MANAGEMENT_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.EVENT_MANAGER,
}
FINANCE_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.FINANCE,
}
MARKETING_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.MARKETING,
}
ACCESS_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.EVENT_MANAGER,
    OrganizationRole.SCANNER_MANAGER,
}


def get_membership(user, organization):
    """Return the legacy compatibility membership, never use it for authority."""
    if not getattr(user, "is_authenticated", False) or not organization:
        return None
    return OrganizationMembership.objects.filter(
        user=user,
        organization=organization,
        is_active=True,
    ).first()


def user_has_org_role(user, organization, roles) -> bool:
    """Deprecated adapter backed by canonical Mandates, not membership.role.

    New code must call ``authorization.services.can`` with a Permission code.
    This exists only so older domain callsites can migrate incrementally without
    keeping OrganizationMembership as a competing authority source.
    """
    if not getattr(user, "is_authenticated", False) or not organization:
        return False
    if getattr(user, "is_superuser", False) or has_platform_authority(user):
        return True
    role_codes = {
        LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE[role]
        for role in roles
        if role in LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE
    }
    if not role_codes:
        return False
    now = timezone.now()
    return Mandate.objects.filter(
        profile=user,
        space=organization,
        scope_type=AuthorityScope.SPACE,
        status=MandateStatus.ACTIVE,
        revoked_at__isnull=True,
        role__code__in=role_codes,
        role__is_active=True,
    ).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=now),
        Q(valid_until__isnull=True) | Q(valid_until__gt=now),
    ).exists()


def organization_has_public_profile(organization) -> bool:
    return bool(
        organization.public_profile
        and organization.verification_status != OrganizationVerificationStatus.SUSPENDED
    )


def user_can_access_organization_workspace(user, organization) -> bool:
    return can(user, PermissionCode.SPACE_VIEW, organization)


def user_can_manage_organization(user, organization) -> bool:
    return can(user, PermissionCode.SPACE_MANAGE, organization)


def user_can_manage_organization_team(user, organization) -> bool:
    return can(user, PermissionCode.SPACE_TEAM_MANAGE, organization)


def user_can_create_events_for_organization(user, organization) -> bool:
    return can(user, PermissionCode.ACTIVITY_MANAGE, organization)


def user_can_manage_organization_event(user, organization) -> bool:
    return can(user, PermissionCode.ACTIVITY_MANAGE, organization)


def user_can_manage_organization_finance(user, organization) -> bool:
    return can(user, PermissionCode.FINANCE_MANAGE, organization)


def user_can_manage_organization_marketing(user, organization) -> bool:
    return can(user, PermissionCode.MARKETING_MANAGE, organization)


def user_can_manage_organization_access(user, organization) -> bool:
    return can(user, PermissionCode.ACCESS_MANAGE, organization)
