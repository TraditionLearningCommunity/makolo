from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .errors import ProspectorContractError
from .frontier import FrontierClaim
from .observation_contracts import ObservationReceipt
from .observation_handoff import ObservationHandoff
from .policy import GateDecision, GateDisposition, ObservationPolicy
from .security import ObservationGate


@dataclass(frozen=True, slots=True)
class SafeHandoffResult:
    decision: GateDecision
    receipt: Optional[ObservationReceipt] = None

    def __post_init__(self) -> None:
        if self.decision.disposition is GateDisposition.ALLOW:
            if not isinstance(self.receipt, ObservationReceipt):
                raise ProspectorContractError(
                    "allowed safe handoff requires an ObservationReceipt"
                )
        elif self.receipt is not None:
            raise ProspectorContractError(
                "rejected/deferred safe handoff must not contact Observateur"
            )


class SafeObservationHandoff:
    """Canonical PX4 path: gate first, Observateur only after ALLOW."""

    def __init__(self, *, gate: ObservationGate, observer) -> None:
        self.gate = gate
        self.handoff = ObservationHandoff(observer=observer)

    async def submit(
        self,
        claim: FrontierClaim,
        *,
        policy: ObservationPolicy,
        requested_at: datetime,
    ) -> SafeHandoffResult:
        decision = await self.gate.evaluate(
            claim,
            policy=policy,
            now=requested_at,
        )
        if decision.disposition is not GateDisposition.ALLOW:
            return SafeHandoffResult(decision=decision)
        receipt = await self.handoff.submit(
            claim,
            requested_at=requested_at,
        )
        return SafeHandoffResult(
            decision=decision,
            receipt=receipt,
        )
