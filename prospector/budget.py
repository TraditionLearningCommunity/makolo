from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping, Optional

from .errors import ProspectorContractError


@dataclass(frozen=True, slots=True)
class BudgetReservationDecision:
    allowed: bool
    retry_at: Optional[datetime]
    scopes: Mapping[str, str]
    reused: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed", bool(self.allowed))
        object.__setattr__(self, "reused", bool(self.reused))
        if self.retry_at is not None:
            if self.retry_at.tzinfo is None or self.retry_at.utcoffset() is None:
                raise ProspectorContractError("budget retry_at must be timezone-aware")
            object.__setattr__(
                self,
                "retry_at",
                self.retry_at.astimezone(timezone.utc),
            )
        if not self.allowed and self.retry_at is None:
            raise ProspectorContractError(
                "denied budget reservation requires retry_at"
            )
        object.__setattr__(self, "scopes", MappingProxyType(dict(self.scopes)))
