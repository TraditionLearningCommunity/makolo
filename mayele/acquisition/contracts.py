from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from mayele.common.contracts import KnowledgeScope
from mayele.common.errors import MayeleContractError
from mayele.common.fingerprints import semantic_fingerprint


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise MayeleContractError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise MayeleContractError(f"{name} must not be empty")
    return normalized


def _aware_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise MayeleContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise MayeleContractError(f"{name} must be timezone-aware")
    return value


class DiscoveryResultStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    INACCESSIBLE = "INACCESSIBLE"


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """A discovery lead. It is not an observed source or world fact."""

    discovery_ref: str
    candidate_locator: str
    discovered_at: datetime
    scope: KnowledgeScope = field(default_factory=KnowledgeScope)
    title: Optional[str] = None
    status: DiscoveryResultStatus = DiscoveryResultStatus.CANDIDATE
    source_ref: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "discovery_ref", _required_text("discovery_ref", self.discovery_ref)
        )
        object.__setattr__(
            self,
            "candidate_locator",
            _required_text("candidate_locator", self.candidate_locator),
        )
        object.__setattr__(
            self, "discovered_at", _aware_datetime("discovered_at", self.discovered_at)
        )
        if not isinstance(self.scope, KnowledgeScope):
            raise MayeleContractError("scope must be KnowledgeScope")
        if self.title is not None:
            object.__setattr__(self, "title", _required_text("title", self.title))
        try:
            status = DiscoveryResultStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid discovery result status") from exc
        object.__setattr__(self, "status", status)
        if self.source_ref is not None:
            object.__setattr__(
                self, "source_ref", _required_text("source_ref", self.source_ref)
            )

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(
            {
                "discovery_ref": self.discovery_ref,
                "candidate_locator": self.candidate_locator,
                "discovered_at": self.discovered_at,
                "scope": self.scope.to_payload(),
                "title": self.title,
                "status": self.status.value,
                "source_ref": self.source_ref,
            }
        )
