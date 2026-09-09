"""Special-relativistic use of prescribed electromagnetic fields."""
from __future__ import annotations

from typing import Callable

from ..bodies import CorpsPhysique
from ..fields import ChampElectromagnetique
from ..systems import Univers
from ..values import Instant, Vecteur3


def force_lorentz_sr(
    charge_c: float,
    vitesse_m_s: Vecteur3,
    champ_e_v_m: Vecteur3,
    champ_b_t: Vecteur3,
) -> Vecteur3:
    """Exact inertial-frame Lorentz three-force ``dp/dt=q(E+v×B)``."""
    return (champ_e_v_m + vitesse_m_s.cross(champ_b_t)) * charge_c


def creer_force_provider_lorentz_sr(
    champ: ChampElectromagnetique,
) -> Callable[[CorpsPhysique, Univers, Instant], Vecteur3]:
    """Create a force provider compatible with ``EvolutionSRCorps``."""

    def provider(body: CorpsPhysique, _univers: Univers, instant: Instant) -> Vecteur3:
        state = body.etat()
        position = state.position()
        velocity = state.vitesse()
        if position is None or velocity is None:
            raise ValueError("Relativistic Lorentz force requires position and velocity")
        electric, magnetic = champ.evaluer(position, instant)
        return force_lorentz_sr(body.charge().value, velocity, electric, magnetic)

    return provider
