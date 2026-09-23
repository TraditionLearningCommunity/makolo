from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from interpreter.contracts import CandidateEntity, InterpretedMaterial

from .contracts import ResolutionAlternative


@dataclass(frozen=True, slots=True)
class EntityLookup:
    families: tuple[str, ...]
    alternatives: tuple[ResolutionAlternative, ...] = ()
    provisional_identity_key: str | None = None
    basis_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FactHistoryComparison:
    status: str | None = None
    related_candidate_refs: tuple[str, ...] = ()
    basis_codes: tuple[str, ...] = ()


class RealityCatalogPort(Protocol):
    def lookup_entity(self, material: InterpretedMaterial, entity: CandidateEntity, context) -> EntityLookup:
        """Return bounded read-only canonical candidates for one interpreted entity."""
        ...


class ResolutionHistoryPort(Protocol):
    def compare_fact(self, *, endpoint, predicate, semantic_fingerprint, material: InterpretedMaterial) -> FactHistoryComparison:
        """Compare one fact against prior finalized resolution assertions."""
        ...


class ResolvedMaterialSourcePort(Protocol):
    def get_material(self, resolution_ref: str):
        """Project one finalized Resolver output for Orchestrator consumption."""
        ...
