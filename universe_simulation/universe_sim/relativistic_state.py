"""Relativistic kinematic state compatible with the conceptual physical model."""
from __future__ import annotations

from dataclasses import dataclass, field

from .relativistic_values import (
    energie_totale_relativiste,
    facteur_lorentz,
    impulsion_relativiste,
    vitesse_depuis_impulsion,
)
from .values import Vecteur3


@dataclass(slots=True)
class EtatCinematiqueRelativiste:
    """Massive-particle kinematics in an inertial coordinate chart.

    ``impulsion`` rather than ``vitesse`` is the independent dynamical
    variable. Rest mass belongs to the body's mass state and is supplied when
    derived quantities are requested. This avoids duplicating physical mass in
    two state components.
    """

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
