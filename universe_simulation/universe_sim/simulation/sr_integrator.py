"""Momentum-based special-relativistic particle integration."""
from __future__ import annotations

from dataclasses import dataclass
from math import asinh, cosh, sinh, tanh

from ..constants import C
from ..relativistic_values import (
    gamma_depuis_impulsion,
    impulsion_relativiste,
    rapidite_depuis_vitesse_scalaire,
    vitesse_depuis_impulsion,
)
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
    """Special-relativistic integration using momentum as state variable."""

    nom: str = "Integrateur relativiste special par impulsion"

    def avancer_force_constante(self, etat: EtatParticuleSR, force_n: Vecteur3, dt_s: float) -> None:
        """Advance under constant coordinate-frame three-force ``dp/dt = F``."""
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

    def avancer_acceleration_propre_colineaire(
        self,
        etat: EtatParticuleSR,
        acceleration_propre_m_s2: float,
        direction: Vecteur3,
        dt_s: float,
        tolerance_perpendiculaire: float = 1e-10,
    ) -> None:
        """Exact propagation for constant collinear proper acceleration.

        The acceleration direction is fixed in the coordinate frame during the
        step. The initial velocity must be collinear with that direction. This
        propagator is useful for idealized accelerate/coast/decelerate mission
        phases and never requires an artificial speed clamp.
        """
        if dt_s <= 0:
            raise ValueError("Positive integration step required")
        axis = direction.normalized()
        velocity = etat.vitesse_m_s
        v_parallel_scalar = velocity.dot(axis)
        v_perp = velocity - axis * v_parallel_scalar
        if v_perp.norm() > tolerance_perpendiculaire * C:
            raise ValueError("Exact proper-acceleration propagator requires collinear initial velocity")
        if acceleration_propre_m_s2 == 0:
            self.avancer_force_constante(etat, Vecteur3.zero(), dt_s)
            return

        eta0 = rapidite_depuis_vitesse_scalaire(v_parallel_scalar)
        eta1 = asinh(sinh(eta0) + acceleration_propre_m_s2 * dt_s / C)
        delta_tau = C * (eta1 - eta0) / acceleration_propre_m_s2
        delta_x = C * C * (cosh(eta1) - cosh(eta0)) / acceleration_propre_m_s2
        v1 = axis * (C * tanh(eta1))

        etat.position_m = etat.position_m + axis * delta_x
        etat.impulsion_kg_m_s = impulsion_relativiste(etat.masse_repos_kg, v1)
        etat.temps_propre_s += delta_tau
