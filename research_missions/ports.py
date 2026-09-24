from __future__ import annotations

from typing import Protocol, Tuple, runtime_checkable

from .contracts import ResearchContext


@runtime_checkable
class ResearchContextSourcePort(Protocol):
    """Read-only lookup from a stable prospecting target to research intent."""

    def contexts_for_target(
        self,
        target_key: str,
    ) -> Tuple[ResearchContext, ...]:
        ...
