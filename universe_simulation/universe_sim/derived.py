"""Trajectories, orbits and physically meaningful derived structures."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4
from .bodies import CorpsPhysique
from .spacetime import PointReference, Referentiel
from .states import EtatPhysique
from .systems import SystemePhysique
from .values import Instant, Vecteur3

@dataclass(slots=True)
class Trajectoire:
    corps_id: str
    referentiel: Referentiel
    etats: list[EtatPhysique] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))
    def ajouter(self, etat: EtatPhysique) -> None: self.etats.append(etat.copier())
    def intervalle(self):
        return None if not self.etats else (self.etats[0].instant, self.etats[-1].instant)

@dataclass(slots=True)
class ReferenceOrbitale:
    nom: str
    corps: CorpsPhysique | None = None
    systeme: SystemePhysique | None = None
    point: PointReference | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    def __post_init__(self) -> None:
        if sum(x is not None for x in (self.corps, self.systeme, self.point)) != 1:
            raise ValueError("ReferenceOrbitale requires exactly one physical/geometric reference")

@dataclass(frozen=True, slots=True)
class ElementsOrbitaux:
    demi_grand_axe: float; excentricite: float; inclinaison: float
    longitude_noeud_ascendant: float; argument_periastre: float; anomalie_vraie: float; epoque: Instant

@dataclass(slots=True)
class Orbite:
    corps: CorpsPhysique
    reference: ReferenceOrbitale
    referentiel: Referentiel
    epoque: Instant
    elements: ElementsOrbitaux | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    def est_elliptique(self) -> bool: return self.elements is not None and self.elements.excentricite < 1.0

@dataclass(slots=True)
class Barycentre(PointReference):
    systeme: SystemePhysique | None = None

class NomPointLagrange(str, Enum):
    L1="L1"; L2="L2"; L3="L3"; L4="L4"; L5="L5"

@dataclass(slots=True)
class PointDeLagrange(PointReference):
    nom_point: NomPointLagrange = NomPointLagrange.L1
    corps_primaire_id: str | None = None
    corps_secondaire_id: str | None = None

@dataclass(slots=True)
class RegionPhysiqueRemarquable:
    nom: str
    centre: Vecteur3 | None = None
    rayon: float | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    def contient(self, point: Vecteur3) -> bool:
        return self.centre is not None and self.rayon is not None and point.distance_to(self.centre) <= self.rayon

@dataclass(slots=True)
class SphereDeHill(RegionPhysiqueRemarquable): pass
@dataclass(slots=True)
class SphereInfluence(RegionPhysiqueRemarquable): pass
@dataclass(slots=True)
class LobeDeRoche(RegionPhysiqueRemarquable):
    approximation: str = "volume-equivalent"
