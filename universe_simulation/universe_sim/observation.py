"""Observers, observations, constellations and asterisms."""
from __future__ import annotations
from dataclasses import dataclass, field
from math import pi
from uuid import uuid4
from .bodies import CorpsPhysique
from .spacetime import Referentiel
from .values import Instant, Vecteur3

def _wrap_2pi(angle: float) -> float:
    return angle % (2.0 * pi)

@dataclass(frozen=True, slots=True)
class RegionCeleste:
    ra_min: float
    ra_max: float
    dec_min: float
    dec_max: float
    nom: str = ""
    def contient(self, ascension_droite: float, declinaison: float) -> bool:
        ra = _wrap_2pi(ascension_droite)
        raw_span = self.ra_max - self.ra_min
        if abs(raw_span) >= 2.0 * pi - 1e-12:
            in_ra = True
        else:
            lo = _wrap_2pi(self.ra_min); hi = _wrap_2pi(self.ra_max)
            in_ra = lo <= ra <= hi if lo <= hi else (ra >= lo or ra <= hi)
        return in_ra and self.dec_min <= declinaison <= self.dec_max

@dataclass(slots=True)
class StructureObservationnelle:
    nom: str
    id: str = field(default_factory=lambda: str(uuid4()))

@dataclass(slots=True)
class Constellation(StructureObservationnelle):
    region: RegionCeleste = field(default_factory=lambda: RegionCeleste(0.0, 2*pi, -pi/2, pi/2))
    convention: str = "IAU-like spherical region"
    def contient(self, ascension_droite: float, declinaison: float) -> bool:
        return self.region.contient(ascension_droite, declinaison)

@dataclass(slots=True)
class Asterisme(StructureObservationnelle):
    sources_ids: list[str] = field(default_factory=list)
    def ajouter_source(self, corps: CorpsPhysique) -> None:
        if corps.id not in self.sources_ids: self.sources_ids.append(corps.id)

@dataclass(slots=True)
class Observateur:
    nom: str
    position: Vecteur3
    referentiel: Referentiel
    vitesse: Vecteur3 = field(default_factory=Vecteur3.zero)
    id: str = field(default_factory=lambda: str(uuid4()))

@dataclass(slots=True)
class Observation:
    observateur: Observateur
    cible: CorpsPhysique
    instant_reception: Instant
    direction_apparente: Vecteur3
    distance_geometrique: float
    ascension_droite: float | None = None
    declinaison: float | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    def projection(self) -> tuple[float | None, float | None]:
        return self.ascension_droite, self.declinaison
