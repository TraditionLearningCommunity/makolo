from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class ConnectionScope(str, Enum):
    PLATFORM = "platform"
    SPACE = "space"
    PROFILE = "profile"


class ConnectionAuthorizationError(PermissionError):
    """Raised when an actor cannot administer or use a Connection."""


class ConnectionUnavailable(ConnectionAuthorizationError):
    """Raised when a Connection is disabled or otherwise unavailable."""


@dataclass(frozen=True, slots=True)
class ConnectionRef:
    """Provider-neutral authorization projection of a persisted Connection.

    It intentionally carries no credential material and no provider-specific
    configuration. The owning domain remains responsible for persistence.
    """

    id: str
    scope: ConnectionScope
    enabled: bool
    profile_id: str | None = None
    space_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Connection id must not be empty.")
        if self.scope == ConnectionScope.PLATFORM and (self.profile_id or self.space_id):
            raise ValueError("A platform Connection cannot target a Profile or Space.")
        if self.scope == ConnectionScope.PROFILE and (not self.profile_id or self.space_id):
            raise ValueError("A profile Connection must target exactly one Profile.")
        if self.scope == ConnectionScope.SPACE and (not self.space_id or self.profile_id):
            raise ValueError("A space Connection must target exactly one Space.")


def authorize_connection(
    *,
    actor_id: str,
    connection: ConnectionRef,
    has_platform_authority: Callable[[], bool],
    has_space_authority: Callable[[str], bool],
) -> None:
    """Authorize Connection use without treating membership as authority.

    A personal Connection belongs to exactly one Profile. Space and platform
    Connections require current Makolo authority supplied by the authorization
    domain. Installed provider availability is deliberately not considered here.
    """

    if not connection.enabled:
        raise ConnectionUnavailable("Connection is disabled.")

    if connection.scope == ConnectionScope.PROFILE:
        if actor_id != connection.profile_id:
            raise ConnectionAuthorizationError("Connection belongs to another Profile.")
        return

    if connection.scope == ConnectionScope.SPACE:
        if not has_space_authority(connection.space_id or ""):
            raise ConnectionAuthorizationError("Current actor has no authority for this Space Connection.")
        return

    if not has_platform_authority():
        raise ConnectionAuthorizationError("Current actor has no platform authority for this Connection.")
