from __future__ import annotations

from datetime import datetime

from .errors import ObservationContractError
from .frontier import FrontierClaim
from .observation_contracts import (
    ObservationReceipt,
    observation_target_from_claim,
)
from .ports import ObserverPort


class ObservationHandoff:
    """Contract-level handoff from a Frontier claim to an Observateur.

    PX3 validates idempotent identity and acknowledgement consistency only.
    Frontier state transitions are deliberately left to PX4/PX6 policy/runtime.
    """

    def __init__(self, *, observer: ObserverPort) -> None:
        self.observer = observer

    async def submit(
        self,
        claim: FrontierClaim,
        *,
        requested_at: datetime,
    ) -> ObservationReceipt:
        target = observation_target_from_claim(claim, requested_at=requested_at)
        receipt = await self.observer.submit(target)
        if not isinstance(receipt, ObservationReceipt):
            raise ObservationContractError(
                "observer must return an ObservationReceipt"
            )
        if (
            receipt.handoff_key != target.handoff_key
            or receipt.target_key != target.target_key
            or receipt.handoff_generation != target.handoff_generation
        ):
            raise ObservationContractError(
                "observer receipt does not acknowledge the submitted handoff"
            )
        return receipt
