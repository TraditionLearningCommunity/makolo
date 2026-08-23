from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from activities.models import Activity
from authorization.constants import (
    PermissionCode,
    STANDARD_ACTIVITY_ROLE_CODES,
    STANDARD_SPACE_ROLE_CODES,
    SystemRoleCode,
)
from authorization.models import AuthorityScope, Mandate, MandateStatus
from authorization.selectors import current_mandates
from authorization.services import (
    can,
    get_system_role,
    grant_activity_role,
    replace_standard_space_role,
    revoke_all_space_mandates,
    revoke_mandate,
)

from .models import Organization, OrganizationMembership, TeamMembership, TeamMembershipStatus
from .services import _legacy_role_code, _sync_legacy_membership


def _lock_space(space):
    return Organization.objects.select_for_update().order_by().get(pk=space.pk)


def _lock_membership(*, membership, space):
    try:
        return (
            TeamMembership.objects.select_for_update()
            .select_related("team__organization", "user")
            .order_by()
            .get(pk=membership.pk, team__organization=space)
        )
    except TeamMembership.DoesNotExist as exc:
        raise ValidationError("Ce membre n'appartient pas à l'Espace courant.") from exc


def _require_active_member(membership):
    if membership.status != TeamMembershipStatus.ACTIVE:
        raise ValidationError("Ce membre n'est plus actif dans l'équipe.")


def _require_team_management(*, actor, space):
    if not can(actor, PermissionCode.SPACE_TEAM_MANAGE, space):
        raise PermissionDenied("Vous ne pouvez pas gérer l'équipe de cet Espace.")


def _is_current_owner(*, profile, space):
    return current_mandates().filter(
        profile=profile,
        scope_type=AuthorityScope.SPACE,
        space=space,
        role__is_system=True,
        role__code=SystemRoleCode.SPACE_OWNER,
    ).exists()


def _require_ownership_management(*, actor, space):
    if not can(actor, PermissionCode.SPACE_OWNERSHIP_MANAGE, space):
        raise PermissionDenied("Seul un propriétaire habilité peut modifier la propriété de cet Espace.")


def _sync_legacy_space_role(*, membership, space, role_code, actor):
    """Update the compatibility projection without replaying it into TeamMembership.

    Existing OrganizationMembership writes emit a compatibility post-save signal
    that projects legacy ``joined_at`` back into TeamMembership. A responsibility
    edit must not change membership history, so an existing projection is updated
    directly. If a historical row is missing, the canonical bridge creates it and
    the original TeamMembership join timestamp is restored afterwards.
    """

    legacy_role = _legacy_role_code(role_code)
    updated = OrganizationMembership.objects.filter(
        organization=space,
        user=membership.user,
    ).update(
        role=legacy_role,
        is_active=True,
        invited_by=actor,
    )
    if updated:
        return

    joined_at = membership.joined_at
    _sync_legacy_membership(
        organization=space,
        user=membership.user,
        canonical_role_code=role_code,
        invited_by=actor,
        active=True,
    )
    TeamMembership.objects.filter(pk=membership.pk).update(joined_at=joined_at)


@transaction.atomic
def update_member_space_responsibility(*, membership, actor, role_code):
    """Replace one member's standard Space responsibility without touching membership history."""

    space = _lock_space(membership.team.organization)
    membership = _lock_membership(membership=membership, space=space)
    _require_active_member(membership)
    _require_team_management(actor=actor, space=space)

    target_role = get_system_role(role_code, scope_type=AuthorityScope.SPACE)
    if target_role.code not in STANDARD_SPACE_ROLE_CODES:
        raise ValidationError("Cette responsabilité n'est pas un rôle standard d'Espace.")

    current_owner = _is_current_owner(profile=membership.user, space=space)
    if current_owner or target_role.code == SystemRoleCode.SPACE_OWNER:
        _require_ownership_management(actor=actor, space=space)

    mandate = replace_standard_space_role(
        profile=membership.user,
        space=space,
        role_code=target_role.code,
        granted_by=actor,
        source="team-responsibility",
    )
    _sync_legacy_space_role(
        membership=membership,
        space=space,
        role_code=target_role.code,
        actor=actor,
    )
    return mandate


@transaction.atomic
def grant_member_activity_responsibility(*, membership, actor, activity, role_code):
    """Grant a supported Activity role to an active member of the Space team."""

    space = _lock_space(membership.team.organization)
    membership = _lock_membership(membership=membership, space=space)
    _require_active_member(membership)
    _require_team_management(actor=actor, space=space)

    try:
        activity = Activity.objects.select_for_update().order_by().get(pk=activity.pk, space=space)
    except Activity.DoesNotExist as exc:
        raise ValidationError("Cette activité n'appartient pas à l'Espace courant.") from exc

    role = get_system_role(role_code, scope_type=AuthorityScope.ACTIVITY)
    if role.code not in STANDARD_ACTIVITY_ROLE_CODES:
        raise ValidationError("Cette responsabilité n'est pas un rôle Activity pris en charge.")

    return grant_activity_role(
        profile=membership.user,
        activity=activity,
        role=role,
        granted_by=actor,
        source="team-responsibility",
    )


@transaction.atomic
def revoke_member_activity_responsibility(*, membership, actor, mandate):
    """Soft-revoke one exact Activity responsibility while keeping team membership active."""

    space = _lock_space(membership.team.organization)
    membership = _lock_membership(membership=membership, space=space)
    _require_active_member(membership)
    _require_team_management(actor=actor, space=space)

    try:
        mandate = (
            Mandate.objects.select_for_update()
            .select_related("activity__space", "role")
            .order_by()
            .get(pk=mandate.pk)
        )
    except Mandate.DoesNotExist as exc:
        raise ValidationError("Cette responsabilité n'existe pas.") from exc

    if (
        mandate.profile_id != membership.user_id
        or mandate.scope_type != AuthorityScope.ACTIVITY
        or mandate.activity_id is None
        or mandate.activity.space_id != space.pk
        or not mandate.role.is_system
        or mandate.role.code not in STANDARD_ACTIVITY_ROLE_CODES
    ):
        raise PermissionDenied("Cette responsabilité ne peut pas être modifiée depuis cet Espace.")

    return revoke_mandate(mandate=mandate, actor=actor)


@transaction.atomic
def remove_member_from_space(*, membership, actor):
    """Deactivate membership and remove authority belonging to this Space only."""

    space = _lock_space(membership.team.organization)
    membership = _lock_membership(membership=membership, space=space)
    _require_active_member(membership)
    _require_team_management(actor=actor, space=space)

    if _is_current_owner(profile=membership.user, space=space):
        _require_ownership_management(actor=actor, space=space)

    # Canonical Space cleanup also enforces the last-owner invariant.
    revoke_all_space_mandates(profile=membership.user, space=space, actor=actor)

    # A complete departure from the Space team also removes local authority on
    # Activities operated by this Space, but deliberately leaves Group,
    # Platform and other-Space mandates untouched.
    activity_mandates = list(
        Mandate.objects.select_for_update()
        .filter(
            profile=membership.user,
            scope_type=AuthorityScope.ACTIVITY,
            activity__space=space,
            status=MandateStatus.ACTIVE,
        )
        .order_by()
    )
    for activity_mandate in activity_mandates:
        revoke_mandate(mandate=activity_mandate, actor=actor)

    membership.status = TeamMembershipStatus.INACTIVE
    membership.save(update_fields=["status", "updated_at"])
    OrganizationMembership.objects.filter(organization=space, user=membership.user).update(is_active=False)
    return membership
