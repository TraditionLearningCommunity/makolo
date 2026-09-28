from __future__ import annotations

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from authorization.services import can
from interoperability.connections import ConnectionRef, ConnectionScope, authorize_connection

from .models import ProviderConnection, ProviderHealth, ProviderScope


def connection_ref(connection: ProviderConnection) -> ConnectionRef:
    """Project Intelligence persistence onto the provider-neutral Connection contract.

    ``ProviderConnection.profile`` points at ``UserProfile`` while Makolo
    authority and authenticated actors use the canonical auth user. The generic
    Profile Connection owner id therefore uses ``UserProfile.user_id`` rather
    than the presentation-profile row id.
    """

    return ConnectionRef(
        id=str(connection.pk),
        scope=ConnectionScope(connection.scope),
        enabled=connection.enabled,
        profile_id=(
            str(connection.profile.user_id)
            if connection.profile_id
            else None
        ),
        space_id=str(connection.space_id) if connection.space_id else None,
    )


def authorize_provider_connection(*, actor, connection: ProviderConnection) -> None:
    """Apply current Makolo authority to an Intelligence provider Connection.

    The provider credential is intentionally absent from the projection. A
    personal Connection is usable only by its owning Profile; Space and
    platform Connections require current Mandate/Permission authority.
    """

    ref = connection_ref(connection)
    authorize_connection(
        actor_id=str(actor.pk),
        connection=ref,
        has_platform_authority=lambda: can(actor, PermissionCode.PLATFORM_MANAGE),
        has_space_authority=lambda _space_id: bool(
            connection.scope == ProviderScope.SPACE
            and connection.space_id
            and has_direct_space_permission(
                actor,
                connection.space,
                PermissionCode.SPACE_MANAGE,
            )
        ),
    )


def provider_connections_for_profile(actor):
    return (
        ProviderConnection.objects.filter(
            scope=ProviderScope.PROFILE,
            profile__user=actor,
        )
        .select_related("profile")
        .prefetch_related("routes")
        .order_by("priority", "name", "id")
    )


def provider_connections_for_space(space):
    return (
        ProviderConnection.objects.filter(scope=ProviderScope.SPACE, space=space)
        .select_related("space")
        .prefetch_related("routes")
        .order_by("priority", "name", "id")
    )


def platform_provider_connections():
    return (
        ProviderConnection.objects.filter(scope=ProviderScope.PLATFORM)
        .prefetch_related("routes")
        .order_by("priority", "name", "id")
    )


def _public_health(value: str) -> str:
    if value in {ProviderHealth.UNAVAILABLE, ProviderHealth.INVALID_CREDENTIALS}:
        return ProviderHealth.UNAVAILABLE
    if value == ProviderHealth.HEALTHY:
        return ProviderHealth.HEALTHY
    if value == ProviderHealth.DEGRADED:
        return ProviderHealth.DEGRADED
    return ProviderHealth.UNKNOWN


def project_provider_connection(connection: ProviderConnection, *, manageable: bool) -> dict:
    capabilities = sorted(
        {route.capability for route in connection.routes.all() if route.enabled}
    )
    usable = bool(
        manageable
        and connection.enabled
        and capabilities
        and connection.health_status
        not in {ProviderHealth.UNAVAILABLE, ProviderHealth.INVALID_CREDENTIALS}
    )
    return {
        "id": str(connection.pk),
        "scope": connection.scope,
        "owner": "intelligence",
        "provider_protocol": connection.protocol,
        "display_name": connection.name,
        "available": True,
        "connected": True,
        "usable": usable,
        "manageable": bool(manageable),
        "enabled": connection.enabled,
        "status": "connected" if connection.enabled else "disabled",
        "health": _public_health(connection.health_status),
        "capabilities": capabilities,
        "permissions": {
            "use": usable,
            "manage": bool(manageable),
        },
    }
