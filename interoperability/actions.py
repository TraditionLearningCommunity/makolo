from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .connections import ConnectionRef
from .registry import InteroperabilityRegistry


class ActionError(RuntimeError):
    pass


class UnknownAction(ActionError):
    pass


class ActionAuthorizationError(ActionError):
    pass


class ActionConnectionRequired(ActionError):
    pass


@dataclass(frozen=True, slots=True)
class ActionExecutionContext:
    actor: Any
    authority_context: Any = None
    connection: ConnectionRef | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    """Stable Makolo action contract.

    The handler must be a domain service or an adapter that delegates to one;
    registering an action never transfers canonical business truth to M7.
    """

    code: str
    capability: str
    owner: str
    handler: Callable[[ActionExecutionContext, Mapping[str, Any]], Any]
    authorize: Callable[[ActionExecutionContext], bool]
    requires_connection: bool = True
    idempotent: bool = False

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("Action code must not be empty.")
        if not self.capability.strip():
            raise ValueError("Action capability must not be empty.")
        if not self.owner.strip():
            raise ValueError("Action owner must not be empty.")
        if not callable(self.handler) or not callable(self.authorize):
            raise ValueError("Action handler and authorization policy must be callable.")


class ActionRegistry:
    def __init__(self, interoperability_registry: InteroperabilityRegistry) -> None:
        self._interoperability_registry = interoperability_registry
        self._actions: dict[str, ActionDefinition] = {}

    def register(self, action: ActionDefinition) -> ActionDefinition:
        self._interoperability_registry.get_capability(action.capability)
        current = self._actions.get(action.code)
        if current is not None and current != action:
            raise ValueError(f"Action {action.code!r} is already registered differently.")
        self._actions[action.code] = action
        return action

    def get(self, code: str) -> ActionDefinition:
        try:
            return self._actions[code]
        except KeyError as exc:
            raise UnknownAction(code) from exc

    def execute(
        self,
        code: str,
        *,
        context: ActionExecutionContext,
        payload: Mapping[str, Any],
        authorize_connection: Callable[[ConnectionRef], None] | None = None,
    ) -> Any:
        action = self.get(code)
        self._interoperability_registry.get_capability(action.capability)

        if not action.authorize(context):
            raise ActionAuthorizationError(code)

        if action.requires_connection:
            if context.connection is None:
                raise ActionConnectionRequired(code)
            if authorize_connection is None:
                raise ActionConnectionRequired(f"{code}: no Connection authorizer supplied")
            authorize_connection(context.connection)

        if action.idempotent and not (context.idempotency_key or "").strip():
            raise ActionError(f"{code}: idempotency key is required")

        return action.handler(context, payload)
