"""Nominal data used only to build reproducible demonstration scenes.

The values are intentionally simple initial conditions, not an ephemeris.
Distances are nominal semi-major axes and the generated planetary examples
start on circularized orbits so the visualization remains understandable.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..constants import AU, EARTH_MASS, EARTH_RADIUS


@dataclass(frozen=True, slots=True)
class PlaneteDemo:
    nom: str
    masse_kg: float
    rayon_m: float
    distance_m: float
    inclinaison_deg: float
    phase_deg: float
    albedo: float | None = None


PLANETES_DEMO: tuple[PlaneteDemo, ...] = (
    PlaneteDemo("Mercure", 3.3011e23, 2.4397e6, 0.38709893 * AU, 7.005, 10.0, 0.142),
    PlaneteDemo("Venus", 4.8675e24, 6.0518e6, 0.72333199 * AU, 3.3946, 72.0, 0.689),
    PlaneteDemo("Terre", EARTH_MASS, EARTH_RADIUS, 1.0 * AU, 0.0, 145.0, 0.306),
    PlaneteDemo("Mars", 6.4171e23, 3.3895e6, 1.52366231 * AU, 1.850, 225.0, 0.170),
    PlaneteDemo("Jupiter", 1.89813e27, 6.9911e7, 5.20336301 * AU, 1.303, 290.0, 0.538),
    PlaneteDemo("Saturne", 5.6834e26, 5.8232e7, 9.53707032 * AU, 2.485, 330.0, 0.499),
    PlaneteDemo("Uranus", 8.6810e25, 2.5362e7, 19.19126393 * AU, 0.773, 35.0, 0.488),
    PlaneteDemo("Neptune", 1.02413e26, 2.4622e7, 30.06896348 * AU, 1.770, 185.0, 0.442),
)
