"""Event-horizon geometry helpers for prescribed black-hole metrics."""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from ..metrics import (
    Coordonnees4,
    Metrique4D,
    MetriqueKerrKerrSchild,
    MetriqueKerrNewmanKerrSchild,
    MetriqueSchwarzschildKerrSchild,
)


@dataclass(frozen=True, slots=True)
class FranchissementHorizon:
    rayon_avant_m: float
    rayon_apres_m: float
    rayon_horizon_m: float
    fraction_pas: float


def rayon_radial(metrique: Metrique4D, x: Coordonnees4) -> float:
    if isinstance(metrique, MetriqueSchwarzschildKerrSchild):
        return sqrt(x[1] * x[1] + x[2] * x[2] + x[3] * x[3])
    if isinstance(metrique, (MetriqueKerrKerrSchild, MetriqueKerrNewmanKerrSchild)):
        return metrique.rayon_boyer_lindquist(x)
    raise TypeError("The selected metric has no black-hole event horizon radius")


def rayon_horizon_externe(metrique: Metrique4D) -> float:
    if isinstance(metrique, MetriqueSchwarzschildKerrSchild):
        return metrique.rayon_schwarzschild_m
    if isinstance(metrique, (MetriqueKerrKerrSchild, MetriqueKerrNewmanKerrSchild)):
        return metrique.rayon_horizon_externe_m
    raise TypeError("The selected metric has no black-hole event horizon")


def est_dans_horizon(metrique: Metrique4D, x: Coordonnees4) -> bool:
    return rayon_radial(metrique, x) <= rayon_horizon_externe(metrique)


def detecter_franchissement_horizon(
    metrique: Metrique4D,
    avant: Coordonnees4,
    apres: Coordonnees4,
) -> FranchissementHorizon | None:
    horizon = rayon_horizon_externe(metrique)
    r0 = rayon_radial(metrique, avant)
    r1 = rayon_radial(metrique, apres)
    if not (r0 > horizon and r1 <= horizon):
        return None
    denominator = r0 - r1
    fraction = 1.0 if denominator == 0 else (r0 - horizon) / denominator
    fraction = min(1.0, max(0.0, fraction))
    return FranchissementHorizon(r0, r1, horizon, fraction)
