from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from .errors import ResolverContractError


@dataclass(frozen=True, slots=True)
class ResolutionClaim:
    resolution_ref: str
    interpretation_ref: str
    material_key: str
    target_key: str
    claim_token: UUID
    claimed_by: str
    lease_expires_at: datetime
    started_at: datetime

    def __post_init__(self):
        for name in (
            "resolution_ref",
            "interpretation_ref",
            "material_key",
            "target_key",
            "claimed_by",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ResolverContractError(f"{name} must not be empty")
        if not isinstance(self.claim_token, UUID):
            raise ResolverContractError("claim_token must be UUID")
        for name in ("lease_expires_at", "started_at"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ResolverContractError(f"{name} must be timezone-aware")
            object.__setattr__(self, name, value.astimezone(timezone.utc))
        if self.lease_expires_at <= self.started_at:
            raise ResolverContractError("lease_expires_at must follow started_at")
