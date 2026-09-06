from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class ExtensionError(RuntimeError):
    pass


class ExtensionSurfaceDenied(ExtensionError):
    pass


@dataclass(frozen=True, slots=True)
class ExtensionDefinition:
    code: str
    actions: frozenset[str]
    events: frozenset[str]
    read_projections: frozenset[str]
    ui_slots: frozenset[str]

    def __init__(
        self,
        *,
        code: str,
        actions: Iterable[str] = (),
        events: Iterable[str] = (),
        read_projections: Iterable[str] = (),
        ui_slots: Iterable[str] = (),
    ) -> None:
        code = code.strip()
        if not code:
            raise ValueError("Extension code must not be empty.")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "actions", frozenset(item.strip() for item in actions if item.strip()))
        object.__setattr__(self, "events", frozenset(item.strip() for item in events if item.strip()))
        object.__setattr__(self, "read_projections", frozenset(item.strip() for item in read_projections if item.strip()))
        object.__setattr__(self, "ui_slots", frozenset(item.strip() for item in ui_slots if item.strip()))


class ExtensionRegistry:
    """Allowlist registry for controlled extension composition.

    Extensions receive contract names only. This registry exposes no ORM, raw
    SQL, filesystem, arbitrary Python execution, credentials or private-data
    bypass. Owner domains keep validation and authorization at execution time.
    """

    def __init__(
        self,
        *,
        allowed_actions: Iterable[str],
        allowed_events: Iterable[str],
        allowed_read_projections: Iterable[str],
        allowed_ui_slots: Iterable[str],
    ) -> None:
        self._allowed_actions = frozenset(allowed_actions)
        self._allowed_events = frozenset(allowed_events)
        self._allowed_read_projections = frozenset(allowed_read_projections)
        self._allowed_ui_slots = frozenset(allowed_ui_slots)
        self._extensions: dict[str, ExtensionDefinition] = {}

    def register(self, extension: ExtensionDefinition) -> ExtensionDefinition:
        denied = {
            "actions": extension.actions - self._allowed_actions,
            "events": extension.events - self._allowed_events,
            "read_projections": extension.read_projections - self._allowed_read_projections,
            "ui_slots": extension.ui_slots - self._allowed_ui_slots,
        }
        denied = {name: values for name, values in denied.items() if values}
        if denied:
            raise ExtensionSurfaceDenied(str(denied))
        current = self._extensions.get(extension.code)
        if current is not None and current != extension:
            raise ValueError(f"Extension {extension.code!r} is already registered differently.")
        self._extensions[extension.code] = extension
        return extension

    def get(self, code: str) -> ExtensionDefinition:
        try:
            return self._extensions[code]
        except KeyError as exc:
            raise ExtensionError(f"Unknown extension: {code}") from exc
