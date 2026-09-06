from __future__ import annotations

from authorization.constants import PermissionCode
from authorization.services import can
from interoperability.connections import ConnectionRef, ConnectionScope, authorize_connection

from .models import ProviderConnection, ProviderScope


def connection_ref(connection: ProviderConnection) -> ConnectionRef:
    return ConnectionRef(
        id=str(connection.pk),
        scope=ConnectionScope(connection.scope),
        enabled=connection.enabled,
        profile_id=str(connection.profile_id) if connection.profile_id else None,
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
            and can(actor, PermissionCode.SPACE_MANAGE, space=connection.space)
        ),
    )
