"""Base interfaces for physical laws and simulation models."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import uuid4
from ..effects import EffetPhysique
from ..systems import Univers
from ..values import Instant

@dataclass(slots=True)
class LoiPhysique(ABC):
    nom: str
    domaine_validite: str = ""
    active: bool = True
    id: str = field(default_factory=lambda: str(uuid4()))
    def est_applicable(self, _contexte: object | None = None) -> bool: return self.active

@dataclass(slots=True)
class ModelePhysique(LoiPhysique):
    niveau_fidelite: str = "macroscopique"
    required_state_components: tuple[str, ...] = ("translation", "massique")
    @abstractmethod
    def evaluer(self, univers: Univers, instant: Instant, gestionnaire_interactions: object | None = None) -> list[EffetPhysique]:
        raise NotImplementedError
