"""Authorized entrypoint for new Space custom roles.

The canonical Role and RolePermission models own the role and its authority.
Subscription only gates admission of a *new* custom Role: it never deletes
existing Role/Mandate facts after a plan downgrade and it never grants rights.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from .constants import PermissionCode
from .models import AuthorityScope, Role
from .services import can


@transaction.atomic
def create_custom_space_role(*, space, actor, code, name, description=""):
    """Create an inert Space Role only when both authority and product gate allow.

    No implicit RolePermission or Mandate is created. Permission composition and
    assignment remain explicit, independent authorization operations.
    """
    from organizations.models import Organization
    from subscriptions.entitlements import resolve_entitlement

    space = Organization.objects.select_for_update().order_by().get(pk=space.pk)
    if not can(actor, PermissionCode.SPACE_TEAM_MANAGE, space):
        raise PermissionDenied("La gestion des rôles de cet Espace n'est pas autorisée.")

    capability = resolve_entitlement(space, "custom_roles")
    if not capability.allowed:
        raise ValidationError({
            "subscription": "La création de rôles personnalisés n'est pas disponible "
                            "avec l'abonnement actuel de cet Espace."
        })

    role = Role(
        code=(code or "").strip(),
        name=(name or "").strip(),
        description=(description or "").strip(),
        scope_type=AuthorityScope.SPACE,
        organization=space,
        is_system=False,
    )
    role.full_clean()
    try:
        role.save()
    except IntegrityError as exc:
        raise ValidationError({"code": "Ce code de rôle est déjà utilisé dans cet Espace."}) from exc
    return role
