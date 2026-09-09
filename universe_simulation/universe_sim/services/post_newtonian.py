"""First post-Newtonian (1PN) two-body relative dynamics.

The implementation uses the standard 1PN relative acceleration in harmonic
coordinates for two non-spinning point masses. It is an approximation for
weak fields and velocities small compared with ``c``; it is not a substitute
for a geodesic integrator in a strong field.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..constants import C, G
from ..values import Vecteur3


@dataclass(frozen=True, slots=True)
class ParametresDeuxCorps1PN:
    masse_1_kg: float
    masse_2_kg: float

    def __post_init__(self) -> None:
        if self.masse_1_kg <= 0 or self.masse_2_kg <= 0:
            raise ValueError("1PN two-body dynamics requires positive masses")

    @property
    def masse_totale_kg(self) -> float:
        return self.masse_1_kg + self.masse_2_kg

    @property
    def mu_gravitationnel(self) -> float:
        return G * self.masse_totale_kg

    @property
    def eta(self) -> float:
        total = self.masse_totale_kg
        return self.masse_1_kg * self.masse_2_kg / (total * total)


def acceleration_relative_1pn(
    position_relative_m: Vecteur3,
    vitesse_relative_m_s: Vecteur3,
    masse_1_kg: float,
    masse_2_kg: float,
    inclure_newtonien: bool = True,
) -> Vecteur3:
    """Return ``d²(r2-r1)/dt²`` through first post-Newtonian order."""
    params = ParametresDeuxCorps1PN(masse_1_kg, masse_2_kg)
    r = position_relative_m.norm()
    if r <= 0:
        raise ValueError("1PN relative acceleration requires non-zero separation")
    n = position_relative_m / r
    v = vitesse_relative_m_s
    v2 = v.norm2()
    rdot = n.dot(v)
    mu = params.mu_gravitationnel
    eta = params.eta

    newton = -n * (mu / (r * r)) if inclure_newtonien else Vecteur3.zero()
    radial = (
        (4.0 + 2.0 * eta) * mu / r
        - (1.0 + 3.0 * eta) * v2
        + 1.5 * eta * rdot * rdot
    )
    tangential = (4.0 - 2.0 * eta) * rdot
    correction = (n * radial + v * tangential) * (mu / (C * C * r * r))
    return newton + correction


def repartir_acceleration_relative(
    acceleration_relative: Vecteur3,
    masse_1_kg: float,
    masse_2_kg: float,
) -> tuple[Vecteur3, Vecteur3]:
    """Split relative acceleration into barycentric component accelerations.

    Returns ``(a1, a2)`` with ``a2-a1 = acceleration_relative`` and zero
    centre-of-mass acceleration for an isolated pair.
    """
    params = ParametresDeuxCorps1PN(masse_1_kg, masse_2_kg)
    total = params.masse_totale_kg
    a1 = acceleration_relative * (-masse_2_kg / total)
    a2 = acceleration_relative * (masse_1_kg / total)
    return a1, a2
