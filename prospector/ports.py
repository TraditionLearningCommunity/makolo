from __future__ import annotations

from datetime import datetime
from typing import Mapping, Optional, Protocol, Sequence, runtime_checkable

from .budget import BudgetReservationDecision
from .contracts import ProspectingCandidate, ProspectingTarget
from .feedback import ProspectingFeedback
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

    async def suppress(
        self,
        claim: FrontierClaim,
        *,
        reason_code: str,
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
class FrontierLookupPort(Protocol):
    """Read-only target lookup used by bounded structural expansion."""

    async def get(self, target_key: str) -> Optional[ProspectingTarget]:
        ...


@runtime_checkable
class DnsResolverPort(Protocol):
    async def resolve(self, hostname: str) -> Sequence[str]:
        ...


@runtime_checkable
class DomainScopePort(Protocol):
    def registrable_domain(self, hostname: str) -> str:
        ...


@runtime_checkable
class BudgetReservationPort(Protocol):
    async def reserve(
        self,
        *,
        handoff_key: str,
        policy_key: str,
        scopes: Mapping[str, str],
        limits: Mapping[str, int],
        period_start: datetime,
        period_end: datetime,
        now: datetime,
    ) -> BudgetReservationDecision:
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
class ProspectingFeedbackSinkPort(Protocol):
    """Downstream outcome feedback boundary for Prospecteur learning."""

    async def record(self, feedback: ProspectingFeedback) -> bool:
        ...


@runtime_checkable
class TargetSinkPort(Protocol):
    """PX0 compatibility port; new handoffs use ObserverPort."""

    async def submit(self, target: ProspectingTarget) -> None:
        ...
