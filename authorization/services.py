from __future__ import annotations

from collections import defaultdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from .constants import (
    PermissionCode,
    STANDARD_SPACE_ROLE_CODES,
    SystemRoleCode,
)
from .models import AuthorityScope, Mandate, MandateStatus, Permission, Role, RolePermission


def _current_mandate_q(at=None) -> Q:
    at = at or timezone.now()
    return (
        Q(status=MandateStatus.ACTIVE, revoked_at__isnull=True)
        & (Q(valid_from__isnull=True) | Q(valid_from__lte=at))
        & (Q(valid_until__isnull=True) | Q(valid_until__gt=at))
    )


def _authenticated(profile) -> bool:
    return bool(profile and getattr(profile, "is_authenticated", False))


def _mandates_with_permissions(profile, *, space=None, at=None):
    queryset = (
        Mandate.objects.filter(profile=profile)
        .filter(_current_mandate_q(at))
        .filter(role__is_active=True)
        .select_related("role", "space")
        .prefetch_related(
            Prefetch(
                "role__role_permissions",
                queryset=RolePermission.objects.select_related("permission").filter(
                    permission__is_active=True
                ),
            )
        )
    )
    if space is not None:
        queryset = queryset.filter(
            Q(scope_type=AuthorityScope.PLATFORM)
            | Q(scope_type=AuthorityScope.SPACE, space=space)
        )
    return queryset


def effective_permission_codes(profile, *, space=None, at=None) -> set[str]:
    """Resolve effective permission codes with one mandate query plus prefetch.

    With ``space=None`` this returns capabilities held anywhere, which is useful
    for navigation. With an Espace it returns platform permissions plus only the
    permissions valid in that Espace.
    """
    if not _authenticated(profile):
        return set()
    if getattr(profile, "is_superuser", False):
        return set(Permission.objects.filter(is_active=True).values_list("code", flat=True))

    codes: set[str] = set()
    for mandate in _mandates_with_permissions(profile, space=space, at=at):
        for link in mandate.role.role_permissions.all():
            permission = link.permission
            if permission.is_active:
                codes.add(permission.code)

    if PermissionCode.PLATFORM_MANAGE in codes:
        codes.update(Permission.objects.filter(is_active=True).values_list("code", flat=True))
    return codes


def can(profile, permission_code: str, space=None, *, at=None) -> bool:
    if not _authenticated(profile):
        return False
    if getattr(profile, "is_superuser", False):
        return True
    return permission_code in effective_permission_codes(profile, space=space, at=at)


def can_many(profile, permission_codes, space=None, *, at=None) -> dict[str, bool]:
    requested = tuple(dict.fromkeys(permission_codes))
    effective = effective_permission_codes(profile, space=space, at=at)
    return {code: code in effective for code in requested}


def has_platform_authority(profile, *, at=None) -> bool:
    return can(profile, PermissionCode.PLATFORM_MANAGE, at=at)


def space_ids_with_permission(profile, permission_code: str, *, at=None):
    """Return authorized Espace ids, or ``None`` when platform authority is global."""
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
        )
        .filter(_current_mandate_q(at))
        .exclude(space_id=None)
        .values_list("space_id", flat=True)
        .distinct()
    )


def get_system_role(code: str, *, scope_type=AuthorityScope.SPACE) -> Role:
    try:
        return Role.objects.get(
            code=code,
            scope_type=scope_type,
            is_system=True,
            is_active=True,
        )
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


@transaction.atomic
def grant_space_role(*, profile, space, role, granted_by=None, source="service") -> Mandate:
    if isinstance(role, str):
        role = get_system_role(role, scope_type=AuthorityScope.SPACE)
    validate_role_for_space(role, space)

    existing = (
        Mandate.objects.select_for_update()
        .filter(
            profile=profile,
            role=role,
            scope_type=AuthorityScope.SPACE,
            space=space,
            status=MandateStatus.ACTIVE,
        )
        .first()
    )
    if existing:
        changed = []
        if existing.revoked_at is not None:
            existing.revoked_at = None
            changed.append("revoked_at")
        if granted_by is not None and existing.granted_by_id != getattr(granted_by, "pk", None):
            existing.granted_by = granted_by
            changed.append("granted_by")
        if source and existing.source != source:
            existing.source = source
            changed.append("source")
        if changed:
            existing.save(update_fields=changed + ["updated_at"])
        return existing

    mandate = Mandate(
        profile=profile,
        role=role,
        scope_type=AuthorityScope.SPACE,
        space=space,
        status=MandateStatus.ACTIVE,
        granted_by=granted_by,
        source=source,
    )
    mandate.full_clean()
    mandate.save()
    return mandate


@transaction.atomic
def ensure_platform_admin_mandate(*, profile, granted_by=None, source="staff-backfill") -> Mandate:
    role = get_system_role(SystemRoleCode.PLATFORM_ADMIN, scope_type=AuthorityScope.PLATFORM)
    existing = (
        Mandate.objects.select_for_update()
        .filter(
            profile=profile,
            role=role,
            scope_type=AuthorityScope.PLATFORM,
            status=MandateStatus.ACTIVE,
        )
        .first()
    )
    if existing:
        return existing
    mandate = Mandate(
        profile=profile,
        role=role,
        scope_type=AuthorityScope.PLATFORM,
        status=MandateStatus.ACTIVE,
        granted_by=granted_by,
        source=source,
    )
    mandate.full_clean()
    mandate.save()
    return mandate


def _current_owner_mandates(space, *, exclude_pk=None, at=None):
    queryset = Mandate.objects.filter(
        space=space,
        scope_type=AuthorityScope.SPACE,
        role__code=SystemRoleCode.SPACE_OWNER,
        role__is_system=True,
        role__is_active=True,
    ).filter(_current_mandate_q(at))
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset


def _assert_owner_can_be_removed(mandate: Mandate) -> None:
    if (
        mandate.scope_type == AuthorityScope.SPACE
        and mandate.space_id
        and mandate.role.code == SystemRoleCode.SPACE_OWNER
        and mandate.status == MandateStatus.ACTIVE
        and not _current_owner_mandates(mandate.space, exclude_pk=mandate.pk).exists()
    ):
        raise ValidationError("Un Espace doit conserver au moins un propriétaire actif.")


@transaction.atomic
def revoke_mandate(*, mandate, actor=None) -> Mandate:
    locked = (
        Mandate.objects.select_for_update()
        .select_related("role", "space", "profile")
        .get(pk=mandate.pk)
    )
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

    current = list(
        Mandate.objects.select_for_update()
        .select_related("role", "space")
        .filter(
            profile=profile,
            space=space,
            scope_type=AuthorityScope.SPACE,
            status=MandateStatus.ACTIVE,
            role__code__in=STANDARD_SPACE_ROLE_CODES,
        )
    )
    for mandate in current:
        if mandate.role_id == target_role.pk:
            continue
        _assert_owner_can_be_removed(mandate)
        mandate.status = MandateStatus.REVOKED
        mandate.revoked_at = timezone.now()
        mandate.save(update_fields=["status", "revoked_at", "updated_at"])

    return grant_space_role(
        profile=profile,
        space=space,
        role=target_role,
        granted_by=granted_by,
        source=source,
    )


@transaction.atomic
def revoke_all_space_mandates(*, profile, space, actor=None) -> int:
    mandates = list(
        Mandate.objects.select_for_update()
        .select_related("role", "space")
        .filter(
            profile=profile,
            space=space,
            scope_type=AuthorityScope.SPACE,
            status=MandateStatus.ACTIVE,
        )
    )
    for mandate in mandates:
        _assert_owner_can_be_removed(mandate)
    now = timezone.now()
    for mandate in mandates:
        mandate.status = MandateStatus.REVOKED
        mandate.revoked_at = now
        mandate.save(update_fields=["status", "revoked_at", "updated_at"])
    return len(mandates)


def primary_space_roles_for_profiles(*, space, profile_ids, at=None) -> dict:
    """Return one display role per profile without an N+1 query."""
    if not profile_ids:
        return {}
    priority = {
        SystemRoleCode.SPACE_OWNER: 0,
        SystemRoleCode.SPACE_ADMIN: 10,
        SystemRoleCode.ACTIVITY_MANAGER: 20,
        SystemRoleCode.FINANCE: 30,
        SystemRoleCode.MARKETING: 40,
        SystemRoleCode.ACCESS_MANAGER: 50,
    }
    mandates = (
        Mandate.objects.filter(
            profile_id__in=profile_ids,
            space=space,
            scope_type=AuthorityScope.SPACE,
            role__is_active=True,
        )
        .filter(_current_mandate_q(at))
        .select_related("role")
    )
    grouped = defaultdict(list)
    for mandate in mandates:
        grouped[mandate.profile_id].append(mandate.role)
    result = {}
    for profile_id, roles in grouped.items():
        result[profile_id] = sorted(
            roles,
            key=lambda role: (priority.get(role.code, 1000), role.name),
        )[0]
    return result


def require(profile, permission_code: str, space=None, *, message=None) -> None:
    if not can(profile, permission_code, space):
        raise PermissionDenied(message or "Vous n'avez pas l'autorisation requise.")
