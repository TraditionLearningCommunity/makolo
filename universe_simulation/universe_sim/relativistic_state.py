"""Relativistic kinematic states used by the conceptual physical model."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .constants import C
from .metrics import Coordonnees4
from .relativistic_values import (
    energie_totale_relativiste,
    facteur_lorentz,
    impulsion_relativiste,
    vitesse_depuis_impulsion,
)
from .values import Vecteur3


@dataclass(slots=True)
class EtatCinematiqueRelativiste:
    """Massive-particle kinematics in a flat inertial coordinate chart."""

    position: Vecteur3 = field(default_factory=Vecteur3.zero)
    impulsion: Vecteur3 = field(default_factory=Vecteur3.zero)
    temps_propre_s: float = 0.0

    def __post_init__(self) -> None:
        if self.temps_propre_s < 0:
            raise ValueError("Accumulated proper time cannot be negative")

    @classmethod
    def depuis_vitesse(
        cls,
        position: Vecteur3,
        vitesse: Vecteur3,
        masse_repos_kg: float,
        temps_propre_s: float = 0.0,
    ) -> "EtatCinematiqueRelativiste":
        return cls(position, impulsion_relativiste(masse_repos_kg, vitesse), temps_propre_s)

    def vitesse(self, masse_repos_kg: float) -> Vecteur3:
        return vitesse_depuis_impulsion(masse_repos_kg, self.impulsion)

    def gamma(self, masse_repos_kg: float) -> float:
        return facteur_lorentz(self.vitesse(masse_repos_kg))

    def energie_totale(self, masse_repos_kg: float) -> float:
        return energie_totale_relativiste(masse_repos_kg, self.impulsion)

    def copier(self) -> "EtatCinematiqueRelativiste":
        return EtatCinematiqueRelativiste(self.position, self.impulsion, self.temps_propre_s)


class TypeCourbeCausale(str, Enum):
    TEMPORELLE = "temporelle"
    NULLE = "nulle"


@dataclass(slots=True)
class EtatSpatioTemporelRelativiste:
    """Coordinate state of a worldline in a prescribed curved space-time.

    The default chart convention used by the built-in metrics is
    ``(ct,x,y,z)`` in metres. ``tangente`` is ``dx^mu/dlambda``. For a massive
    timelike path normalized with ``lambda=c*tau``, ``temps_propre_s`` tracks
    the accumulated proper time. Null curves have no proper time.
    """

    coordonnees_m: Coordonnees4
    tangente: Coordonnees4
    parametre_affine_m: float = 0.0
    type_causal: TypeCourbeCausale = TypeCourbeCausale.TEMPORELLE
    temps_propre_s: float | None = 0.0
    carte_coordonnees: str = "ct,x,y,z"

    def __post_init__(self) -> None:
        if self.type_causal == TypeCourbeCausale.NULLE:
            if self.temps_propre_s not in (None, 0.0):
                raise ValueError("A null worldline does not accumulate proper time")
            self.temps_propre_s = None
        elif self.temps_propre_s is None or self.temps_propre_s < 0:
            raise ValueError("A timelike worldline requires non-negative accumulated proper time")

    def temps_coordonne_s(self) -> float:
        return self.coordonnees_m[0] / C

    def position_cartesienne(self) -> Vecteur3:
        return Vecteur3(self.coordonnees_m[1], self.coordonnees_m[2], self.coordonnees_m[3])

    def vitesse_coordonnees(self) -> Vecteur3:
        u0 = self.tangente[0]
        if u0 == 0:
            raise ValueError("Coordinate velocity is undefined for zero temporal tangent component")
        return Vecteur3(
            C * self.tangente[1] / u0,
            C * self.tangente[2] / u0,
            C * self.tangente[3] / u0,
        )

    def copier(self) -> "EtatSpatioTemporelRelativiste":
        return EtatSpatioTemporelRelativiste(
            self.coordonnees_m,
            self.tangente,
            self.parametre_affine_m,
            self.type_causal,
            self.temps_propre_s,
            self.carte_coordonnees,
        )
