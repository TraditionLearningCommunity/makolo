"""Special-relativistic value objects and kinematic conversions in SI units."""
from __future__ import annotations

from dataclasses import dataclass
from math import atanh, isfinite, sqrt, tanh

from .constants import C
from .values import Vecteur3


@dataclass(frozen=True, slots=True)
class Quadrivecteur:
    """Generic four-vector using a temporal component with spatial units.

    For an event displacement the temporal component is ``c * dt``. For a
    four-momentum it is ``E / c``. Homogeneous units make the Minkowski norm
    explicit and avoid silently mixing seconds with metres.
    """

    temporel: float
    spatial: Vecteur3

    def norme_minkowski2(self) -> float:
        return -self.temporel * self.temporel + self.spatial.norm2()


@dataclass(frozen=True, slots=True)
class Quadrimpulsion:
    energie_sur_c: float
    impulsion: Vecteur3

    @property
    def energie(self) -> float:
        return self.energie_sur_c * C

    def invariant_masse2(self) -> float:
        return (self.energie_sur_c * self.energie_sur_c - self.impulsion.norm2()) / (C * C)


def _valider_masse(masse_repos_kg: float) -> None:
    if masse_repos_kg <= 0 or not isfinite(masse_repos_kg):
        raise ValueError("Positive finite rest mass required")


def facteur_lorentz(vitesse: Vecteur3) -> float:
    beta2 = vitesse.norm2() / (C * C)
    if beta2 < 0 or beta2 >= 1:
        raise ValueError("Special relativity requires |v| < c")
    return 1.0 / sqrt(1.0 - beta2)


def impulsion_relativiste(masse_repos_kg: float, vitesse: Vecteur3) -> Vecteur3:
    _valider_masse(masse_repos_kg)
    return vitesse * (facteur_lorentz(vitesse) * masse_repos_kg)


def energie_totale_relativiste(masse_repos_kg: float, impulsion: Vecteur3) -> float:
    _valider_masse(masse_repos_kg)
    return sqrt((impulsion.norm() * C) ** 2 + (masse_repos_kg * C * C) ** 2)


def quadrimpulsion_depuis_vitesse(masse_repos_kg: float, vitesse: Vecteur3) -> Quadrimpulsion:
    p = impulsion_relativiste(masse_repos_kg, vitesse)
    return Quadrimpulsion(energie_totale_relativiste(masse_repos_kg, p) / C, p)


def vitesse_depuis_impulsion(masse_repos_kg: float, impulsion: Vecteur3) -> Vecteur3:
    energie = energie_totale_relativiste(masse_repos_kg, impulsion)
    return impulsion * (C * C / energie)


def gamma_depuis_impulsion(masse_repos_kg: float, impulsion: Vecteur3) -> float:
    energie = energie_totale_relativiste(masse_repos_kg, impulsion)
    return energie / (masse_repos_kg * C * C)


def energie_cinetique_relativiste(masse_repos_kg: float, impulsion: Vecteur3) -> float:
    return energie_totale_relativiste(masse_repos_kg, impulsion) - masse_repos_kg * C * C


def increment_temps_propre(dt_coordonne_s: float, masse_repos_kg: float, impulsion: Vecteur3) -> float:
    if dt_coordonne_s < 0:
        raise ValueError("Coordinate-time increment must be non-negative")
    return dt_coordonne_s / gamma_depuis_impulsion(masse_repos_kg, impulsion)


def rapidite_depuis_vitesse_scalaire(vitesse_m_s: float) -> float:
    beta = vitesse_m_s / C
    if abs(beta) >= 1:
        raise ValueError("Rapidity requires |v| < c")
    return atanh(beta)


def vitesse_scalaire_depuis_rapidite(rapidite: float) -> float:
    return C * tanh(rapidite)
