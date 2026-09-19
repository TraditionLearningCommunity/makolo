from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .contracts import ProspectingTarget
from .errors import ProspectorContractError


class FrontierState(str, Enum):
    READY = "ready"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    SUPPRESSED = "suppressed"


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ProspectorContractError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ProspectorContractError(f"{name} must not be empty")
    return normalized


def _utc_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ProspectorContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProspectorContractError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class FrontierClaim:
    """Lease proving that one worker currently owns a Frontier target."""

    claim_token: str
    worker_id: str
    leased_until: datetime
    target: ProspectingTarget
    handoff_generation: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "claim_token",
            _required_text("claim_token", self.claim_token),
        )
        object.__setattr__(self, "worker_id", _required_text("worker_id", self.worker_id))
        object.__setattr__(
            self,
            "leased_until",
            _utc_datetime("leased_until", self.leased_until),
        )
        if not isinstance(self.target, ProspectingTarget):
            raise ProspectorContractError("target must be a ProspectingTarget")
        if (
            not isinstance(self.handoff_generation, int)
            or isinstance(self.handoff_generation, bool)
            or self.handoff_generation < 1
        ):
            raise ProspectorContractError(
                "handoff_generation must be a positive integer"
            )
