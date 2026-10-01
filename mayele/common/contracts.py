from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .errors import MayeleContractError


class ScopeVisibility(str, Enum):
    PUBLIC = "public"
    RESTRICTED = "restricted"
    PRIVATE = "private"


@dataclass(frozen=True, slots=True)
class KnowledgeScope:
    """Minimal visibility scope; it grants no Makolo authority."""

    visibility: ScopeVisibility = ScopeVisibility.PUBLIC
    context_ref: Optional[str] = None

    def __post_init__(self) -> None:
        try:
            visibility = ScopeVisibility(self.visibility)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid knowledge scope visibility") from exc
        object.__setattr__(self, "visibility", visibility)

        if self.context_ref is not None:
            if not isinstance(self.context_ref, str) or not self.context_ref.strip():
                raise MayeleContractError("context_ref must be a non-empty string")
            object.__setattr__(self, "context_ref", self.context_ref.strip())

        if visibility is not ScopeVisibility.PUBLIC and self.context_ref is None:
            raise MayeleContractError(
                "restricted and private knowledge require an explicit context_ref"
            )

    def to_payload(self) -> dict[str, str | None]:
        return {
            "visibility": self.visibility.value,
            "context_ref": self.context_ref,
        }
