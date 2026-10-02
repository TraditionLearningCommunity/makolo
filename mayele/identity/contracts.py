from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from mayele.cognition import InterpretationReferent
from mayele.common.contracts import KnowledgeScope, ScopeVisibility
from mayele.common.errors import MayeleContractError
from mayele.knowledge import Reality


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise MayeleContractError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise MayeleContractError(f"{name} must not be empty")
    return normalized


def _optional_text(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _required_text(name, value)


def _aware_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise MayeleContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise MayeleContractError(f"{name} must be timezone-aware")
    return value


def _scope_rank(scope: KnowledgeScope) -> int:
    return {
        ScopeVisibility.PUBLIC: 0,
        ScopeVisibility.RESTRICTED: 1,
        ScopeVisibility.PRIVATE: 2,
    }[scope.visibility]


def _derived_scope(
    parent: KnowledgeScope, child: Optional[KnowledgeScope]
) -> KnowledgeScope:
    if not isinstance(parent, KnowledgeScope):
        raise MayeleContractError("referent_scope must be KnowledgeScope")
    if child is None:
        return parent
    if not isinstance(child, KnowledgeScope):
        raise MayeleContractError("scope must be KnowledgeScope")
    if _scope_rank(child) < _scope_rank(parent):
        raise MayeleContractError("knowledge scope cannot be widened implicitly")
    if parent.context_ref is not None and child.context_ref != parent.context_ref:
        raise MayeleContractError(
            "derived non-public knowledge must preserve its parent context_ref"
        )
    return child


class IdentityResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    PROVISIONAL = "PROVISIONAL"
    UNRESOLVED = "UNRESOLVED"


class IdentityResolutionBasisKind(str, Enum):
    MENTION = "MENTION"
    REALITY_CANDIDATE = "REALITY_CANDIDATE"
    REALITY = "REALITY"
    OBSERVED_STATEMENT = "OBSERVED_STATEMENT"
    INTERPRETATION = "INTERPRETATION"
    SOURCE = "SOURCE"
    EXTERNAL_IDENTIFIER = "EXTERNAL_IDENTIFIER"
    DISTINGUISHING_SIGNAL = "DISTINGUISHING_SIGNAL"


@dataclass(frozen=True, slots=True)
class IdentityResolutionBasis:
    """A traceable identity-resolution signal, not epistemic KnowledgeSupport."""

    kind: IdentityResolutionBasisKind
    ref: str

    def __post_init__(self) -> None:
        try:
            kind = IdentityResolutionBasisKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid identity resolution basis kind") from exc
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "ref", _required_text("ref", self.ref))

    def to_payload(self) -> dict[str, str]:
        return {"kind": self.kind.value, "ref": self.ref}


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    """Mayele's identity decision for one unresolved MY3 referent."""

    resolution_ref: str
    referent: InterpretationReferent
    referent_scope: KnowledgeScope
    resolved_at: datetime
    status: IdentityResolutionStatus
    reality: Optional[Reality] = None
    alternatives: Tuple[Reality, ...] = ()
    basis: Tuple[IdentityResolutionBasis, ...] = ()
    method_ref: Optional[str] = None
    method_version: Optional[str] = None
    supersedes_resolution_ref: Optional[str] = None
    scope: Optional[KnowledgeScope] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "resolution_ref", _required_text("resolution_ref", self.resolution_ref)
        )
        if not isinstance(self.referent, InterpretationReferent):
            raise MayeleContractError("referent must be InterpretationReferent")
        if not isinstance(self.referent_scope, KnowledgeScope):
            raise MayeleContractError("referent_scope must be KnowledgeScope")
        object.__setattr__(
            self, "resolved_at", _aware_datetime("resolved_at", self.resolved_at)
        )
        try:
            status = IdentityResolutionStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise MayeleContractError("invalid identity resolution status") from exc
        object.__setattr__(self, "status", status)

        if self.reality is not None and not isinstance(self.reality, Reality):
            raise MayeleContractError("reality must be Reality or None")
        if status in (
            IdentityResolutionStatus.RESOLVED,
            IdentityResolutionStatus.PROVISIONAL,
        ) and self.reality is None:
            raise MayeleContractError(f"{status.value} requires a selected Reality")
        if status is IdentityResolutionStatus.UNRESOLVED and self.reality is not None:
            raise MayeleContractError("UNRESOLVED must not select a Reality")

        alternatives = tuple(self.alternatives)
        if not all(isinstance(item, Reality) for item in alternatives):
            raise MayeleContractError("alternatives must contain Reality values")
        refs = [item.reality_ref for item in alternatives]
        if len(set(refs)) != len(refs):
            raise MayeleContractError("identity alternatives must be unique")
        if self.reality is not None and self.reality.reality_ref in refs:
            raise MayeleContractError(
                "selected Reality must not be duplicated in alternatives"
            )
        object.__setattr__(self, "alternatives", alternatives)

        basis = tuple(self.basis)
        if not basis:
            raise MayeleContractError("identity resolution requires traceable basis")
        if not all(isinstance(item, IdentityResolutionBasis) for item in basis):
            raise MayeleContractError(
                "basis must contain IdentityResolutionBasis values"
            )
        basis_keys = {(item.kind.value, item.ref) for item in basis}
        if len(basis_keys) != len(basis):
            raise MayeleContractError("identity resolution basis must be unique")
        object.__setattr__(self, "basis", basis)

        object.__setattr__(
            self, "method_ref", _optional_text("method_ref", self.method_ref)
        )
        object.__setattr__(
            self,
            "method_version",
            _optional_text("method_version", self.method_version),
        )
        if self.method_version is not None and self.method_ref is None:
            raise MayeleContractError("method_version requires method_ref")

        object.__setattr__(
            self,
            "supersedes_resolution_ref",
            _optional_text(
                "supersedes_resolution_ref", self.supersedes_resolution_ref
            ),
        )
        if self.supersedes_resolution_ref == self.resolution_ref:
            raise MayeleContractError("a resolution cannot supersede itself")

        object.__setattr__(
            self, "scope", _derived_scope(self.referent_scope, self.scope)
        )
