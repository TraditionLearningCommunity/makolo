"""Momentum-based special-relativistic particle integration."""
from __future__ import annotations

from dataclasses import dataclass

from ..relativistic_values import gamma_depuis_impulsion, vitesse_depuis_impulsion
from ..values import Vecteur3


@dataclass(slots=True)
class EtatParticuleSR:
    """Hot numerical state for a massive particle in flat space-time.

    Momentum, not velocity, is the evolved dynamical variable. Rest mass is
    kept explicit here because this lightweight state is numerical rather than
    the long-lived physical identity of a ``CorpsPhysique``.
    """

    position_m: Vecteur3
    impulsion_kg_m_s: Vecteur3
    masse_repos_kg: float
    temps_propre_s: float = 0.0

    def __post_init__(self) -> None:
        if self.masse_repos_kg <= 0:
            raise ValueError("Positive rest mass required")
        if self.temps_propre_s < 0:
            raise ValueError("Proper time cannot be negative in this accumulated state")

    @property
    def vitesse_m_s(self) -> Vecteur3:
        return vitesse_depuis_impulsion(self.masse_repos_kg, self.impulsion_kg_m_s)

    @property
    def gamma(self) -> float:
        return gamma_depuis_impulsion(self.masse_repos_kg, self.impulsion_kg_m_s)


@dataclass(slots=True)
class IntegrateurRelativisteSpecial:
    """Second-order drift with coordinate-frame three-force ``dp/dt = F``.

    Position and accumulated proper time use endpoint-averaged kinematics.
    This path is intentionally independent from Newtonian ``F / m -> dv/dt``.
    """

    nom: str = "Integrateur relativiste special par impulsion"

    def avancer_force_constante(self, etat: EtatParticuleSR, force_n: Vecteur3, dt_s: float) -> None:
        if dt_s <= 0:
            raise ValueError("Positive integration step required")
        p0 = etat.impulsion_kg_m_s
        v0 = vitesse_depuis_impulsion(etat.masse_repos_kg, p0)
        g0 = gamma_depuis_impulsion(etat.masse_repos_kg, p0)

        p1 = p0 + force_n * dt_s
        v1 = vitesse_depuis_impulsion(etat.masse_repos_kg, p1)
        g1 = gamma_depuis_impulsion(etat.masse_repos_kg, p1)

        etat.position_m = etat.position_m + (v0 + v1) * (0.5 * dt_s)
        etat.impulsion_kg_m_s = p1
        etat.temps_propre_s += 0.5 * dt_s * (1.0 / g0 + 1.0 / g1)
