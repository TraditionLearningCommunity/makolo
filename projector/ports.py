from __future__ import annotations

from typing import Protocol

from .contracts import UniverseDelta, UniverseSnapshot


class UniverseProjectionPort(Protocol):
    """Provider-neutral Actor 8 input boundary.

    Actor 8 treats snapshots as authoritative for the declared scope and
    deltas as fenced by each root source_revision. A lower revision must never
    overwrite a higher revision for the same projection root.
    """

    def apply_snapshot(self, snapshot: UniverseSnapshot) -> None: ...

    def apply_delta(self, delta: UniverseDelta) -> None: ...
