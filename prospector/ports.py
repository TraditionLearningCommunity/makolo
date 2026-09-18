from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence, runtime_checkable

from .contracts import ProspectingCandidate, ProspectingTarget
from .frontier import FrontierClaim
from .observation_contracts import (
    ObservationReceipt,
    ObservationReport,
    ObservationTarget,
)
from .source_contracts import ProspectingMission, SourceBatch, SourceCheckpoint


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
class ExternalIndexSourcePort(Protocol):
    name: str

    async def discover(
        self,
        mission: ProspectingMission,
        *,
        checkpoint: Optional[SourceCheckpoint] = None,
    ) -> SourceBatch:
        ...


@runtime_checkable
class SourceCheckpointPort(Protocol):
    async def load(
        self,
        *,
        source_name: str,
        mission_key: str,
        mission_fingerprint: str,
    ) -> Optional[SourceCheckpoint]:
        ...

    async def save(self, checkpoint: SourceCheckpoint) -> None:
        ...


@runtime_checkable
class ObserverPort(Protocol):
    """Durable admission boundary owned by the Observateur."""

    async def submit(self, target: ObservationTarget) -> ObservationReceipt:
        ...


@runtime_checkable
class ObservationReportSinkPort(Protocol):
    """Prospecteur-side boundary for structure-only Observateur feedback."""

    async def submit_report(self, report: ObservationReport) -> None:
        ...


@runtime_checkable
class TargetSinkPort(Protocol):
    """PX0 compatibility port; new handoffs use ObserverPort."""

    async def submit(self, target: ProspectingTarget) -> None:
        ...
