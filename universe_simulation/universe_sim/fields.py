"""Physical fields, potentials, media, radiation and matter distributions."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from math import exp
from typing import Callable, Generic, TypeVar
from uuid import uuid4

from .states import EtatPhysique
from .values import GrandeurPhysique, Instant, Vecteur3

T = TypeVar("T")


@dataclass(slots=True)
class DistributionMatiere:
    masse_totale: GrandeurPhysique | None = None
    densite_provider: Callable[[Vecteur3, Instant], float] | None = None
    description: str = ""

    def densite(self, position: Vecteur3, instant: Instant) -> float:
        if self.densite_provider is None:
            return 0.0
        return max(0.0, self.densite_provider(position, instant))


class ChampPhysique(ABC, Generic[T]):
    def __init__(self, nom: str, sources: list[object] | None = None) -> None:
        self.id = str(uuid4())
        self.nom = nom
        self.sources = list(sources or [])

    @abstractmethod
    def evaluer(self, position: Vecteur3, instant: Instant) -> T:
        raise NotImplementedError


class ChampGravitationnel(ChampPhysique[Vecteur3]):
    def __init__(self, nom: str, provider: Callable[[Vecteur3, Instant], Vecteur3], sources: list[object] | None = None) -> None:
        super().__init__(nom, sources)
        self.provider = provider

    def evaluer(self, position: Vecteur3, instant: Instant) -> Vecteur3:
        return self.provider(position, instant)


class ChampElectrique(ChampPhysique[Vecteur3]):
    def __init__(self, nom: str, provider: Callable[[Vecteur3, Instant], Vecteur3], sources: list[object] | None = None) -> None:
        super().__init__(nom, sources)
        self.provider = provider

    def evaluer(self, position: Vecteur3, instant: Instant) -> Vecteur3:
        return self.provider(position, instant)


class ChampMagnetique(ChampPhysique[Vecteur3]):
    def __init__(self, nom: str, provider: Callable[[Vecteur3, Instant], Vecteur3], sources: list[object] | None = None) -> None:
        super().__init__(nom, sources)
        self.provider = provider

    def evaluer(self, position: Vecteur3, instant: Instant) -> Vecteur3:
        return self.provider(position, instant)


@dataclass(slots=True)
class ChampElectromagnetique:
    electrique: ChampElectrique
    magnetique: ChampMagnetique

    def evaluer(self, position: Vecteur3, instant: Instant) -> tuple[Vecteur3, Vecteur3]:
        return self.electrique.evaluer(position, instant), self.magnetique.evaluer(position, instant)


class PotentielPhysique(ABC):
    @abstractmethod
    def evaluer(self, position: Vecteur3, instant: Instant) -> float:
        raise NotImplementedError


@dataclass(slots=True)
class PotentielGravitationnel(PotentielPhysique):
    provider: Callable[[Vecteur3, Instant], float]

    def evaluer(self, position: Vecteur3, instant: Instant) -> float:
        return self.provider(position, instant)


@dataclass(slots=True)
class PotentielElectrique(PotentielPhysique):
    provider: Callable[[Vecteur3, Instant], float]

    def evaluer(self, position: Vecteur3, instant: Instant) -> float:
        return self.provider(position, instant)


@dataclass(slots=True)
class PotentielEffectif(PotentielPhysique):
    provider: Callable[[Vecteur3, Instant], float]

    def evaluer(self, position: Vecteur3, instant: Instant) -> float:
        return self.provider(position, instant)


class MilieuPhysique(ABC):
    nom: str

    @abstractmethod
    def densite(self, position: Vecteur3, instant: Instant) -> float:
        raise NotImplementedError

    def vitesse_fluide(self, position: Vecteur3, instant: Instant) -> Vecteur3:
        return Vecteur3.zero()


@dataclass(slots=True)
class Atmosphere(MilieuPhysique):
    nom: str = "Atmosphere"
    densite_surface: float = 1.225
    hauteur_echelle: float = 8_500.0
    rayon_reference: float = 6_371_000.0
    rotation_angulaire: Vecteur3 = field(default_factory=Vecteur3.zero)
    pression_surface: float = 101_325.0

    def densite(self, position: Vecteur3, instant: Instant) -> float:
        altitude = max(0.0, position.norm() - self.rayon_reference)
        return self.densite_surface * exp(-altitude / self.hauteur_echelle)

    def pression(self, position: Vecteur3, instant: Instant) -> float:
        altitude = max(0.0, position.norm() - self.rayon_reference)
        return self.pression_surface * exp(-altitude / self.hauteur_echelle)

    def vitesse_fluide(self, position: Vecteur3, instant: Instant) -> Vecteur3:
        return self.rotation_angulaire.cross(position)


@dataclass(slots=True)
class Rayonnement:
    luminosite: GrandeurPhysique
    origine_provider: Callable[[Instant], Vecteur3] = lambda _t: Vecteur3.zero()

    def flux_a(self, position: Vecteur3, instant: Instant) -> float:
        r = position.distance_to(self.origine_provider(instant))
        if r == 0:
            raise ValueError("Radiative flux undefined at source center")
        from math import pi
        return self.luminosite.value / (4.0 * pi * r * r)


@dataclass(slots=True)
class VentStellaire:
    vitesse_provider: Callable[[Vecteur3, Instant], Vecteur3]
    densite_provider: Callable[[Vecteur3, Instant], float]

    def vitesse(self, position: Vecteur3, instant: Instant) -> Vecteur3:
        return self.vitesse_provider(position, instant)

    def densite(self, position: Vecteur3, instant: Instant) -> float:
        return max(0.0, self.densite_provider(position, instant))
