from .models import (
    OrganizationMembership,
    OrganizationRole,
    OrganizationVerificationStatus,
)


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
    if not getattr(user, "is_authenticated", False) or not organization:
        return None
    return OrganizationMembership.objects.filter(
        user=user,
        organization=organization,
        is_active=True,
    ).first()


def user_has_org_role(user, organization, roles) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    membership = get_membership(user, organization)
    return bool(membership and membership.role in roles)


def organization_has_public_profile(organization) -> bool:
    return bool(
        organization.public_profile
        and organization.verification_status != OrganizationVerificationStatus.SUSPENDED
    )


def user_can_access_organization_workspace(user, organization) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    return get_membership(user, organization) is not None


def user_can_manage_organization(user, organization) -> bool:
    return user_has_org_role(user, organization, MANAGE_ORGANIZATION_ROLES)


def user_can_create_events_for_organization(user, organization) -> bool:
    return user_has_org_role(user, organization, EVENT_MANAGEMENT_ROLES)


def user_can_manage_organization_event(user, organization) -> bool:
    return user_has_org_role(user, organization, EVENT_MANAGEMENT_ROLES)


def user_can_manage_organization_finance(user, organization) -> bool:
    return user_has_org_role(user, organization, FINANCE_ROLES)


def user_can_manage_organization_marketing(user, organization) -> bool:
    return user_has_org_role(user, organization, MARKETING_ROLES)


def user_can_manage_organization_access(user, organization) -> bool:
    return user_has_org_role(user, organization, ACCESS_ROLES)
