"""Relativistic concepts kept separate from the classical force engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
from uuid import uuid4
from .effects import EffetPhysique
from .laws.base import ModelePhysique
from .services.relativity import metrique_schwarzschild, rayon_schwarzschild
from .systems import Univers
from .values import Instant

@dataclass(frozen=True, slots=True)
class EvenementEspaceTemps:
    t: float; x: float; y: float; z: float
    def coordonnees(self): return self.t, self.x, self.y, self.z

@dataclass(slots=True)
class LigneUnivers:
    evenements: list[EvenementEspaceTemps] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))
    def ajouter(self, evenement: EvenementEspaceTemps) -> None:
        if self.evenements and evenement.t < self.evenements[-1].t:
            raise ValueError("Worldline events must be time ordered in this coordinate chart")
        self.evenements.append(evenement)

@dataclass(slots=True)
class MetriqueEspaceTemps:
    provider: Callable[[EvenementEspaceTemps], tuple[tuple[float, ...], ...]]
    def evaluer(self, evenement): return self.provider(evenement)

class TypeIntervalle(str, Enum):
    TEMPOREL="temporel"; SPATIAL="spatial"; NUL="nul"

@dataclass(slots=True)
class ConeDeLumiere:
    evenement: EvenementEspaceTemps
    def classer_minkowski(self, autre: EvenementEspaceTemps, c: float = 299_792_458.0, tolerance: float = 1e-9) -> TypeIntervalle:
        dt=autre.t-self.evenement.t; dx=autre.x-self.evenement.x; dy=autre.y-self.evenement.y; dz=autre.z-self.evenement.z
        interval=-(c*dt)**2+dx*dx+dy*dy+dz*dz
        if abs(interval)<=tolerance: return TypeIntervalle.NUL
        return TypeIntervalle.TEMPOREL if interval<0 else TypeIntervalle.SPATIAL

@dataclass(slots=True)
class HorizonEvenements:
    corps_source_id: str
    rayon: float
    modele: str = "Schwarzschild"
    def contient_rayon(self, r: float) -> bool: return r <= self.rayon

@dataclass(slots=True)
class ModeleGravitationRelativiste(ModelePhysique):
    masse_source: float = 0.0
    nom: str = "Gravitation relativiste Schwarzschild"
    domaine_validite: str = "spherical, non-rotating, uncharged central source"
    niveau_fidelite: str = "general relativity - Schwarzschild geometry"
    def horizon(self) -> HorizonEvenements: return HorizonEvenements("source", rayon_schwarzschild(self.masse_source))
    def metrique(self, r: float, theta: float): return metrique_schwarzschild(self.masse_source, r, theta)
    def evaluer(self, univers: Univers, instant: Instant, gestionnaire_interactions: object | None = None) -> list[EffetPhysique]:
        raise RuntimeError("ModeleGravitationRelativiste requires a geodesic/worldline integrator, not the classical force engine")
