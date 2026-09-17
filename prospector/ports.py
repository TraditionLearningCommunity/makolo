from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence, runtime_checkable

from .contracts import ProspectingCandidate, ProspectingTarget
from .frontier import FrontierClaim


@runtime_checkable
class FrontierPort(Protocol):
    """Durable admission and lease boundary for prospecting targets."""

    async def admit(self, candidate: ProspectingCandidate) -> ProspectingTarget:
        ...

    async def claim(
        self,
        *,
        worker_id: str,
        limit: int,
        lease_seconds: int = 300,
    ) -> Sequence[FrontierClaim]:
        ...

    async def complete(self, claim: FrontierClaim) -> ProspectingTarget:
        ...

    async def defer(
        self,
        claim: FrontierClaim,
        *,
        available_at: datetime,
    ) -> ProspectingTarget:
        ...

    async def requeue(
        self,
        *,
        target_key: str,
        available_at: Optional[datetime] = None,
    ) -> ProspectingTarget:
        ...


@runtime_checkable
class TargetSinkPort(Protocol):
    """Minimal outbound boundary for targets ready for a downstream actor."""

    async def submit(self, target: ProspectingTarget) -> None:
        ...
