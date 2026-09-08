"""Space-time models, frames and coordinate systems."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from math import atan2, cos, sin, sqrt
from typing import Callable
from uuid import uuid4

from .constants import C
from .values import Instant, Quaternion, Vecteur3


class TypeModeleEspaceTemps(str, Enum):
    CLASSIQUE = "classique"
    RELATIVISTE = "relativiste"


class ClassificationReferentiel(str, Enum):
    INERTIEL = "inertiel"
    NON_INERTIEL = "non_inertiel"
    APPROXIMATIVEMENT_INERTIEL = "approximativement_inertiel"


class TypeCoordonnees(str, Enum):
    CARTESIEN = "cartesien"
    SPHERIQUE = "spherique"
    CYLINDRIQUE = "cylindrique"
    EQUATORIAL = "equatorial"
    ECLIPTIQUE = "ecliptique"
    GALACTIQUE = "galactique"
    AUTRE = "autre"


class ModeleEspaceTemps(ABC):
    type_modele: TypeModeleEspaceTemps
    dimension_spatiale: int

    @abstractmethod
    def est_valide(self, coords: tuple[float, ...]) -> bool:
        raise NotImplementedError


@dataclass(slots=True)
class ModeleEspaceTempsClassique(ModeleEspaceTemps):
    dimension_spatiale: int = 3
    type_modele: TypeModeleEspaceTemps = TypeModeleEspaceTemps.CLASSIQUE
    temps_global: bool = True

    def est_valide(self, coords: tuple[float, ...]) -> bool:
        return len(coords) == 3

    def distance(self, p1: Vecteur3, p2: Vecteur3) -> float:
        return p1.distance_to(p2)

    def norme(self, v: Vecteur3) -> float:
        return v.norm()


@dataclass(slots=True)
class ModeleEspaceTempsRelativiste(ModeleEspaceTemps):
    metric_provider: Callable[[tuple[float, float, float, float]], tuple[tuple[float, ...], ...]] | None = None
    convention_signature: str = "-+++"
    dimension_spatiale: int = 3
    type_modele: TypeModeleEspaceTemps = TypeModeleEspaceTemps.RELATIVISTE

    def est_valide(self, coords: tuple[float, ...]) -> bool:
        return len(coords) == 4

    def intervalle(self, e1: tuple[float, float, float, float], e2: tuple[float, float, float, float]) -> float:
        dx = tuple(b - a for a, b in zip(e1, e2))
        if self.metric_provider is None:
            return -(C * dx[0]) ** 2 + dx[1] ** 2 + dx[2] ** 2 + dx[3] ** 2
        g = self.metric_provider(e1)
        return sum(g[i][j] * dx[i] * dx[j] for i in range(4) for j in range(4))

    def classer_intervalle(self, value: float, tolerance: float = 1e-9) -> str:
        if abs(value) <= tolerance:
            return "nul"
        return "temporel" if value < 0 else "spatial"


@dataclass(slots=True)
class PointReference:
    nom: str
    position_provider: Callable[[Instant], Vecteur3] = lambda _t: Vecteur3.zero()
    id: str = field(default_factory=lambda: str(uuid4()))

    def position_a(self, instant: Instant, referentiel: "Referentiel | None" = None) -> Vecteur3:
        return self.position_provider(instant)


@dataclass(slots=True)
class Referentiel:
    nom: str
    origine: PointReference
    orientation_provider: Callable[[Instant], Quaternion] = lambda _t: Quaternion.identity()
    velocity_provider: Callable[[Instant], Vecteur3] = lambda _t: Vecteur3.zero()
    vitesse_angulaire: Vecteur3 = field(default_factory=Vecteur3.zero)
    parent: "Referentiel | None" = None
    classification: ClassificationReferentiel = ClassificationReferentiel.INERTIEL
    id: str = field(default_factory=lambda: str(uuid4()))

    def est_inertiel(self, _contexte: object | None = None) -> bool:
        return self.classification == ClassificationReferentiel.INERTIEL

    def origine_a(self, instant: Instant) -> Vecteur3:
        return self.origine.position_a(instant, self.parent)

    def orientation_a(self, instant: Instant) -> Quaternion:
        return self.orientation_provider(instant).normalized()

    def vitesse_origine_a(self, instant: Instant) -> Vecteur3:
        return self.velocity_provider(instant)


@dataclass(frozen=True, slots=True)
class SystemeCoordonnees:
    nom: str = "Cartesian SI"
    type: TypeCoordonnees = TypeCoordonnees.CARTESIEN
    unite_longueur: str = "m"
    unite_angle: str = "rad"
    convention: str = "right-handed"

    def valider(self, coordonnees: tuple[float, ...]) -> bool:
        return len(coordonnees) == 3


def cartesien_vers_spherique(v: Vecteur3) -> tuple[float, float, float]:
    r = v.norm()
    if r == 0:
        return 0.0, 0.0, 0.0
    theta = atan2(v.y, v.x)
    phi = atan2(v.z, sqrt(v.x * v.x + v.y * v.y))
    return r, theta, phi


def spherique_vers_cartesien(r: float, theta: float, phi: float) -> Vecteur3:
    cp = cos(phi)
    return Vecteur3(r * cp * cos(theta), r * cp * sin(theta), r * sin(phi))


ORIGINE_GLOBALE = PointReference("Origine globale")
REFERENTIEL_INERTIEL = Referentiel("Referentiel inertiel global", ORIGINE_GLOBALE)
COORDONNEES_CARTESIENNES = SystemeCoordonnees()
