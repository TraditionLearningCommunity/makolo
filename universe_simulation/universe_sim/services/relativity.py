from __future__ import annotations

from math import pi, sqrt
from typing import TYPE_CHECKING

from ..constants import C, G
from ..metrics import (
    Metrique4D,
    MetriqueKerrKerrSchild,
    MetriqueKerrNewmanKerrSchild,
    MetriqueSchwarzschildKerrSchild,
)

if TYPE_CHECKING:
    from ..bodies import TrouNoir

HBAR = 1.054571817e-34
K_B = 1.380649e-23


def rayon_schwarzschild(masse: float) -> float:
    if masse < 0:
        raise ValueError("Mass must be non-negative")
    return 2.0 * G * masse / (C * C)


def metrique_schwarzschild(masse: float, r: float, theta: float):
    """Legacy static Schwarzschild coordinates, singular at the horizon."""
    rs = rayon_schwarzschild(masse)
    if r <= rs:
        raise ValueError("Static Schwarzschild coordinates are singular at or inside the horizon")
    from math import sin

    f = 1.0 - rs / r
    return (
        (-f * C * C, 0.0, 0.0, 0.0),
        (0.0, 1.0 / f, 0.0, 0.0),
        (0.0, 0.0, r * r, 0.0),
        (0.0, 0.0, 0.0, r * r * sin(theta) ** 2),
    )


def metrique_trou_noir_parametrique(
    masse_kg: float,
    spin_dimensionnel: float = 0.0,
    charge_c: float = 0.0,
) -> Metrique4D:
    """Return an horizon-penetrating stationary metric for a black hole.

    Selection is Schwarzschild for zero spin/charge, Kerr for spin only and
    Kerr-Newman whenever electric charge is non-zero. Reissner-Nordstrom is the
    spin-zero Kerr-Newman special case.
    """
    if charge_c != 0.0:
        return MetriqueKerrNewmanKerrSchild(masse_kg, spin_dimensionnel, charge_c)
    if abs(spin_dimensionnel) < 1e-15:
        return MetriqueSchwarzschildKerrSchild(masse_kg)
    return MetriqueKerrKerrSchild(masse_kg, spin_dimensionnel)


def metrique_pour_trou_noir(trou_noir: "TrouNoir") -> Metrique4D:
    return metrique_trou_noir_parametrique(
        trou_noir.masse().value,
        trou_noir.parametre_spin(),
        trou_noir.charge_bh.value,
    )


def decalage_gravitationnel_schwarzschild(
    masse: float,
    rayon_emission: float,
    rayon_reception: float = float("inf"),
) -> float:
    rs = rayon_schwarzschild(masse)
    if rayon_emission <= rs:
        raise ValueError("Emission radius must be outside the horizon")
    numerator = 1.0 if rayon_reception == float("inf") else 1.0 - rs / rayon_reception
    return sqrt(numerator / (1.0 - rs / rayon_emission)) - 1.0


def temperature_hawking(masse: float) -> float:
    if masse <= 0:
        raise ValueError("Positive mass required")
    return HBAR * C**3 / (8.0 * pi * G * masse * K_B)
