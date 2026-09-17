from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from .contracts import ProspectingCandidate, ProspectingTarget


@runtime_checkable
class FrontierPort(Protocol):
    """Durable admission/claim boundary for prospecting targets.

    PX0 defines the dependency direction only. PX1 owns persistence,
    canonical target keys, concurrency and lifecycle semantics.
    """

    async def admit(self, candidate: ProspectingCandidate) -> ProspectingTarget:
        ...

    async def claim(self, *, limit: int) -> Sequence[ProspectingTarget]:
        ...


@runtime_checkable
class TargetSinkPort(Protocol):
    """Minimal outbound boundary for targets ready for a downstream actor.

    The precise Prospecteur -> Observateur acknowledgement contract is deferred
    to its dedicated checkpoint; the core depends only on target submission.
    """

    async def submit(self, target: ProspectingTarget) -> None:
        ...
