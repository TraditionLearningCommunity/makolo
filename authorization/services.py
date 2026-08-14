from __future__ import annotations

from collections import defaultdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from .constants import (
    PermissionCode,
    STANDARD_ACTIVITY_ROLE_CODES,
    STANDARD_GROUP_ROLE_CODES,
    STANDARD_SPACE_ROLE_CODES,
    SystemRoleCode,
)
from .models import AuthorityScope, Mandate, MandateStatus, Permission, Role, RolePermission


ACTIVITY_PERMISSION_INHERITANCE = {
    PermissionCode.ACTIVITY_VIEW: PermissionCode.SPACE_ACTIVITIES_VIEW,
    PermissionCode.ACTIVITY_MANAGE: PermissionCode.SPACE_ACTIVITIES_MANAGE,
    PermissionCode.ACTIVITY_REQUESTS_VIEW: PermissionCode.SPACE_ACTIVITIES_VIEW,
    PermissionCode.ACTIVITY_REQUESTS_DECIDE: PermissionCode.SPACE_ACTIVITIES_MANAGE,
    PermissionCode.ACTIVITY_ACCESS_VIEW: PermissionCode.SPACE_ACTIVITIES_VIEW,
    PermissionCode.ACTIVITY_ACCESS_MANAGE: PermissionCode.SPACE_ACTIVITIES_MANAGE,
}


def _current_mandate_q(at=None) -> Q:
    at = at or timezone.now()
    return (
        Q(status=MandateStatus.ACTIVE, revoked_at__isnull=True)
        & (Q(valid_from__isnull=True) | Q(valid_from__lte=at))
        & (Q(valid_until__isnull=True) | Q(valid_until__gt=at))
    )


def _authenticated(profile) -> bool:
    return bool(profile and getattr(profile, "is_authenticated", False))


def _mandates_with_permissions(profile, *, space=None, group=None, activity=None, at=None):
    queryset = (
        Mandate.objects.filter(profile=profile)
        .filter(_current_mandate_q(at))
        .filter(role__is_active=True)
        .select_related("role", "space", "group", "activity")
        .prefetch_related(
            Prefetch(
                "role__role_permissions",
                queryset=RolePermission.objects.select_related("permission").filter(permission__is_active=True),
            )
        )
    )
    if activity is not None:
        queryset = queryset.filter(Q(scope_type=AuthorityScope.PLATFORM) | Q(scope_type=AuthorityScope.ACTIVITY, activity=activity))
    elif group is not None:
        queryset = queryset.filter(Q(scope_type=AuthorityScope.PLATFORM) | Q(scope_type=AuthorityScope.GROUP, group=group))
    elif space is not None:
        queryset = queryset.filter(Q(scope_type=AuthorityScope.PLATFORM) | Q(scope_type=AuthorityScope.SPACE, space=space))
    return queryset


def effective_permission_codes(profile, *, space=None, group=None, activity=None, at=None) -> set[str]:
    if not _authenticated(profile):
        return set()
    if getattr(profile, "is_superuser", False):
        return set(Permission.objects.filter(is_active=True).values_list("code", flat=True))
    codes = {
        link.permission.code
        for mandate in _mandates_with_permissions(profile, space=space, group=group, activity=activity, at=at)
        for link in mandate.role.role_permissions.all()
        if link.permission.is_active
    }
    if PermissionCode.PLATFORM_MANAGE in codes:
        codes.update(Permission.objects.filter(is_active=True).values_list("code", flat=True))
    return codes


def can(profile, permission_code: str, space=None, *, group=None, activity=None, at=None) -> bool:
    if not _authenticated(profile):
        return False
    if getattr(profile, "is_superuser", False):
        return True
    if permission_code in effective_permission_codes(profile, space=space, group=group, activity=activity, at=at):
        return True
    if activity is not None and getattr(activity, "space_id", None):
        inherited = ACTIVITY_PERMISSION_INHERITANCE.get(permission_code)
        if inherited:
            return inherited in effective_permission_codes(profile, space=activity.space, at=at)
    return False


def can_many(profile, permission_codes, space=None, *, group=None, activity=None, at=None) -> dict[str, bool]:
    requested = tuple(dict.fromkeys(permission_codes))
    if activity is not None:
        return {code: can(profile, code, space, group=group, activity=activity, at=at) for code in requested}
    effective = effective_permission_codes(profile, space=space, group=group, at=at)
    return {code: code in effective for code in requested}


def has_platform_authority(profile, *, at=None) -> bool:
    return can(profile, PermissionCode.PLATFORM_MANAGE, at=at)


def space_ids_with_permission(profile, permission_code: str, *, at=None):
    if not _authenticated(profile):
        return []
    if getattr(profile, "is_superuser", False) or has_platform_authority(profile, at=at):
        return None
    return list(
        Mandate.objects.filter(
            profile=profile,
            scope_type=AuthorityScope.SPACE,
            role__is_active=True,
            role__role_permissions__permission__code=permission_code,
            role__role_permissions__permission__is_active=True,
        ).filter(_current_mandate_q(at)).exclude(space_id=None).values_list("space_id", flat=True).distinct()
    )


def group_ids_with_permission(profile, permission_code: str, *, at=None):
    if not _authenticated(profile):
        return []
    if getattr(profile, "is_superuser", False) or has_platform_authority(profile, at=at):
        return None
    return list(
        Mandate.objects.filter(
            profile=profile,
            scope_type=AuthorityScope.GROUP,
            role__is_active=True,
            role__role_permissions__permission__code=permission_code,
            role__role_permissions__permission__is_active=True,
        ).filter(_current_mandate_q(at)).exclude(group_id=None).values_list("group_id", flat=True).distinct()
    )


def activity_ids_with_permission(profile, permission_code: str, *, at=None):
    if not _authenticated(profile):
        return []
    if getattr(profile, "is_superuser", False) or has_platform_authority(profile, at=at):
        return None
    direct = set(
        Mandate.objects.filter(
            profile=profile,
            scope_type=AuthorityScope.ACTIVITY,
            role__is_active=True,
            role__role_permissions__permission__code=permission_code,
            role__role_permissions__permission__is_active=True,
        ).filter(_current_mandate_q(at)).exclude(activity_id=None).values_list("activity_id", flat=True).distinct()
    )
    inherited_code = ACTIVITY_PERMISSION_INHERITANCE.get(permission_code)
    if inherited_code:
        space_ids = space_ids_with_permission(profile, inherited_code, at=at)
        if space_ids is None:
            return None
        if space_ids:
            from activities.models import Activity
            direct.update(Activity.objects.filter(space_id__in=space_ids).values_list("pk", flat=True))
    return list(direct)


def get_system_role(code: str, *, scope_type=AuthorityScope.SPACE) -> Role:
    # Compatibility: the historical Python constant ACTIVITY_MANAGER remains
    # the Space-scoped portfolio role. When callers explicitly request an
    # Activity-scoped role, resolve it to the new local manager role.
    if scope_type == AuthorityScope.ACTIVITY and code == SystemRoleCode.ACTIVITY_MANAGER:
        code = SystemRoleCode.ACTIVITY_LOCAL_MANAGER
    try:
        return Role.objects.get(code=code, scope_type=scope_type, is_system=True, is_active=True)
    except Role.DoesNotExist as exc:
        raise ValidationError(f"Le rôle système « {code} » n'est pas disponible.") from exc


def validate_role_for_space(role: Role, space) -> None:
    if not role.is_active or role.scope_type != AuthorityScope.SPACE:
        raise ValidationError("Ce rôle ne peut pas être accordé dans un Espace.")
    if role.is_system:
        if role.organization_id is not None:
            raise ValidationError("Un rôle système Espace ne doit pas appartenir à un Espace précis.")
    elif role.organization_id != space.pk:
        raise ValidationError("Ce rôle personnalisé appartient à un autre Espace.")


def validate_role_for_group(role: Role) -> None:
    if not role.is_active or role.scope_type != AuthorityScope.GROUP or not role.is_system:
        raise ValidationError("Ce rôle ne peut pas être accordé dans un Groupe.")
    if role.organization_id is not None or role.code not in STANDARD_GROUP_ROLE_CODES:
        raise ValidationError("Ce rôle Groupe n'est pas un rôle système pris en charge.")


def validate_role_for_activity(role: Role) -> None:
    if not role.is_active or role.scope_type != AuthorityScope.ACTIVITY or not role.is_system:
        raise ValidationError("Ce rôle ne peut pas être accordé sur une Activité.")
    if role.organization_id is not None or role.code not in STANDARD_ACTIVITY_ROLE_CODES:
        raise ValidationError("Ce rôle Activité n'est pas un rôle système pris en charge.")


@transaction.atomic
def grant_space_role(*, profile, space, role, granted_by=None, source="service") -> Mandate:
    if isinstance(role, str):
        role = get_system_role(role, scope_type=AuthorityScope.SPACE)
    validate_role_for_space(role, space)
    existing = Mandate.objects.select_for_update().filter(profile=profile, role=role, scope_type=AuthorityScope.SPACE, space=space, status=MandateStatus.ACTIVE).order_by().first()
    if existing:
        return existing
    mandate = Mandate(profile=profile, role=role, scope_type=AuthorityScope.SPACE, space=space, status=MandateStatus.ACTIVE, granted_by=granted_by, source=source)
    mandate.full_clean()
    mandate.save()
    return mandate


@transaction.atomic
def grant_group_role(*, profile, group, role, granted_by=None, source="group-service") -> Mandate:
    if isinstance(role, str):
        role = get_system_role(role, scope_type=AuthorityScope.GROUP)
    validate_role_for_group(role)
    existing = Mandate.objects.select_for_update().filter(profile=profile, role=role, scope_type=AuthorityScope.GROUP, group=group, status=MandateStatus.ACTIVE).order_by().first()
    if existing:
        return existing
    mandate = Mandate(profile=profile, role=role, scope_type=AuthorityScope.GROUP, group=group, status=MandateStatus.ACTIVE, granted_by=granted_by, source=source)
    mandate.full_clean()
    mandate.save()
    return mandate


@transaction.atomic
def grant_activity_role(*, profile, activity, role=SystemRoleCode.ACTIVITY_MANAGER, granted_by=None, source="activity-service") -> Mandate:
    if isinstance(role, str):
        role = get_system_role(role, scope_type=AuthorityScope.ACTIVITY)
    validate_role_for_activity(role)
    existing = Mandate.objects.select_for_update().filter(profile=profile, role=role, scope_type=AuthorityScope.ACTIVITY, activity=activity, status=MandateStatus.ACTIVE).order_by().first()
    if existing:
        return existing
    mandate = Mandate(profile=profile, role=role, scope_type=AuthorityScope.ACTIVITY, activity=activity, status=MandateStatus.ACTIVE, granted_by=granted_by, source=source)
    mandate.full_clean()
    mandate.save()
    return mandate


@transaction.atomic
def ensure_platform_admin_mandate(*, profile, granted_by=None, source="staff-backfill") -> Mandate:
    role = get_system_role(SystemRoleCode.PLATFORM_ADMIN, scope_type=AuthorityScope.PLATFORM)
    existing = Mandate.objects.select_for_update().filter(profile=profile, role=role, scope_type=AuthorityScope.PLATFORM, status=MandateStatus.ACTIVE).order_by().first()
    if existing:
        return existing
    mandate = Mandate(profile=profile, role=role, scope_type=AuthorityScope.PLATFORM, status=MandateStatus.ACTIVE, granted_by=granted_by, source=source)
    mandate.full_clean()
    mandate.save()
    return mandate


def _current_owner_mandates(space, *, exclude_pk=None, at=None):
    queryset = Mandate.objects.filter(space=space, scope_type=AuthorityScope.SPACE, role__code=SystemRoleCode.SPACE_OWNER, role__is_system=True, role__is_active=True).filter(_current_mandate_q(at))
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset


def _assert_owner_can_be_removed(mandate: Mandate) -> None:
    if mandate.scope_type == AuthorityScope.SPACE and mandate.space_id and mandate.role.code == SystemRoleCode.SPACE_OWNER and mandate.status == MandateStatus.ACTIVE and not _current_owner_mandates(mandate.space, exclude_pk=mandate.pk).exists():
        raise ValidationError("Un Espace doit conserver au moins un propriétaire actif.")
    if mandate.scope_type == AuthorityScope.GROUP and mandate.group_id and mandate.role.code == SystemRoleCode.GROUP_OWNER and mandate.status == MandateStatus.ACTIVE:
        group = mandate.group
        if group.status == "active" and group.owner_profile_id is not None and group.owner_profile_id == mandate.profile_id:
            raise ValidationError("Le propriétaire d’un Groupe personnel doit transférer la propriété ou archiver le Groupe avant de perdre son Mandat propriétaire.")


@transaction.atomic
def revoke_mandate(*, mandate, actor=None) -> Mandate:
    locked = Mandate.objects.select_for_update().order_by().get(pk=mandate.pk)
    if locked.status == MandateStatus.REVOKED:
        return locked
    _assert_owner_can_be_removed(locked)
    locked.status = MandateStatus.REVOKED
    locked.revoked_at = timezone.now()
    locked.save(update_fields=["status", "revoked_at", "updated_at"])
    return locked


@transaction.atomic
def replace_standard_space_role(*, profile, space, role_code: str, granted_by=None, source="team-service") -> Mandate:
    target_role = get_system_role(role_code, scope_type=AuthorityScope.SPACE)
    if target_role.code not in STANDARD_SPACE_ROLE_CODES:
        raise ValidationError("Ce rôle n'est pas un rôle standard d'Espace.")
    current = list(Mandate.objects.select_for_update().filter(profile=profile, space=space, scope_type=AuthorityScope.SPACE, status=MandateStatus.ACTIVE, role__code__in=STANDARD_SPACE_ROLE_CODES).order_by())
    for mandate in current:
        if mandate.role_id == target_role.pk:
            continue
        _assert_owner_can_be_removed(mandate)
        mandate.status = MandateStatus.REVOKED
        mandate.revoked_at = timezone.now()
        mandate.save(update_fields=["status", "revoked_at", "updated_at"])
    return grant_space_role(profile=profile, space=space, role=target_role, granted_by=granted_by, source=source)


@transaction.atomic
def replace_standard_group_role(*, profile, group, role_code: str, granted_by=None, source="group-service") -> Mandate:
    target_role = get_system_role(role_code, scope_type=AuthorityScope.GROUP)
    validate_role_for_group(target_role)
    current = list(Mandate.objects.select_for_update().filter(profile=profile, group=group, scope_type=AuthorityScope.GROUP, status=MandateStatus.ACTIVE, role__code__in=STANDARD_GROUP_ROLE_CODES).order_by())
    for mandate in current:
        if mandate.role_id == target_role.pk:
            continue
        _assert_owner_can_be_removed(mandate)
        mandate.status = MandateStatus.REVOKED
        mandate.revoked_at = timezone.now()
        mandate.save(update_fields=["status", "revoked_at", "updated_at"])
    return grant_group_role(profile=profile, group=group, role=target_role, granted_by=granted_by, source=source)


@transaction.atomic
def revoke_all_space_mandates(*, profile, space, actor=None) -> int:
    mandates = list(Mandate.objects.select_for_update().filter(profile=profile, space=space, scope_type=AuthorityScope.SPACE, status=MandateStatus.ACTIVE).order_by())
    for mandate in mandates:
        _assert_owner_can_be_removed(mandate)
    now = timezone.now()
    for mandate in mandates:
        mandate.status = MandateStatus.REVOKED
        mandate.revoked_at = now
        mandate.save(update_fields=["status", "revoked_at", "updated_at"])
    return len(mandates)


def primary_space_roles_for_profiles(*, space, profile_ids, at=None) -> dict:
    if not profile_ids:
        return {}
    priority = {SystemRoleCode.SPACE_OWNER: 0, SystemRoleCode.SPACE_ADMIN: 10, SystemRoleCode.SPACE_ACTIVITY_MANAGER: 20, SystemRoleCode.FINANCE: 30, SystemRoleCode.MARKETING: 40, SystemRoleCode.ACCESS_MANAGER: 50}
    mandates = Mandate.objects.filter(profile_id__in=profile_ids, space=space, scope_type=AuthorityScope.SPACE, role__is_active=True).filter(_current_mandate_q(at)).select_related("role")
    grouped = defaultdict(list)
    for mandate in mandates:
        grouped[mandate.profile_id].append(mandate.role)
    return {profile_id: sorted(roles, key=lambda role: (priority.get(role.code, 1000), role.name))[0] for profile_id, roles in grouped.items()}


def primary_group_roles_for_profiles(*, group, profile_ids, at=None) -> dict:
    if not profile_ids:
        return {}
    priority = {SystemRoleCode.GROUP_OWNER: 0, SystemRoleCode.GROUP_ADMIN: 10, SystemRoleCode.GROUP_MODERATOR: 20}
    mandates = Mandate.objects.filter(profile_id__in=profile_ids, group=group, scope_type=AuthorityScope.GROUP, role__is_active=True).filter(_current_mandate_q(at)).select_related("role")
    grouped = defaultdict(list)
    for mandate in mandates:
        grouped[mandate.profile_id].append(mandate.role)
    return {profile_id: sorted(roles, key=lambda role: (priority.get(role.code, 1000), role.name))[0] for profile_id, roles in grouped.items()}


def require(profile, permission_code: str, space=None, *, group=None, activity=None, message=None) -> None:
    if not can(profile, permission_code, space, group=group, activity=activity):
        raise PermissionDenied(message or "Vous n'avez pas l'autorisation requise.")