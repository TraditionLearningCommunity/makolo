"""Vectorized special-relativistic evolution for large vehicle populations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..constants import C
from ..events import EvenementPhysique
from ..regimes import RegimeDynamique
from ..systems import Univers
from ..values import Instant
from .array_backend import ArrayStateBackend, _REGIME_TO_CODE, _vitesses_sr_depuis_impulsions


ForceProviderPopulationSR = Callable[[ArrayStateBackend, Univers, Instant], np.ndarray]


def _force_nulle(backend: ArrayStateBackend, _univers: Univers, _instant: Instant) -> np.ndarray:
    return np.zeros_like(backend.momenta_kg_m_s)


@dataclass(slots=True)
class IntegrateurPopulationSRTableau:
    """Second-order midpoint propagation in coordinate time for SR particles.

    Rest masses are fixed during one call. Variable-mass relativistic rockets
    remain on the dedicated Ackeret/rocket path.
    """

    nom: str = "SR population midpoint momentum"

    @staticmethod
    def _velocites_et_gamma(momentum: np.ndarray, masses: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        velocity = _vitesses_sr_depuis_impulsions(momentum, masses)
        p_norm = np.hypot(
            np.hypot(np.abs(momentum[:, 0]), np.abs(momentum[:, 1])),
            np.abs(momentum[:, 2]),
        )
        gamma = np.hypot(1.0, p_norm / (masses * C))
        return velocity, gamma

    def avancer_forces_constantes(self, backend: ArrayStateBackend, forces_n: np.ndarray, dt_s: float) -> None:
        dt = float(dt_s)
        if dt <= 0:
            raise ValueError("Time step must be positive")
        sr_code = _REGIME_TO_CODE[RegimeDynamique.RELATIVISTE_SPECIAL]
        if np.any(backend.regime_codes != sr_code):
            raise ValueError("SR population integrator accepts only special-relativistic array rows")
        if np.any(backend.masses_kg <= 0):
            raise ValueError("SR population rows require positive rest mass")
        forces = np.asarray(forces_n, dtype=np.float64)
        if forces.shape != backend.momenta_kg_m_s.shape:
            raise ValueError("forces_n must have shape (N,3)")
        active = backend.active
        if not np.any(active):
            return

        p0 = backend.momenta_kg_m_s[active]
        f = forces[active]
        masses = backend.masses_kg[active]
        p_mid = p0 + 0.5 * f * dt
        velocity_mid, gamma_mid = self._velocites_et_gamma(p_mid, masses)
        backend.positions_m[active] += velocity_mid * dt
        backend.momenta_kg_m_s[active] = p0 + f * dt
        finite_tau = np.isfinite(backend.proper_times_s[active])
        tau = backend.proper_times_s[active].copy()
        tau[finite_tau] += dt / gamma_mid[finite_tau]
        backend.proper_times_s[active] = tau
        backend.rafraichir_vitesses()


@dataclass(slots=True)
class EvolutionPopulationSRTableau:
    corps_selectionnes: tuple[str, ...]
    force_provider: ForceProviderPopulationSR = _force_nulle
    integrateur: IntegrateurPopulationSRTableau = field(default_factory=IntegrateurPopulationSRTableau)
    backend: ArrayStateBackend | None = None
    regime: RegimeDynamique = field(default=RegimeDynamique.RELATIVISTE_SPECIAL, init=False)

    @property
    def corps_ids(self) -> tuple[str, ...]:
        return self.corps_selectionnes

    def avancer(self, univers: Univers, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        bodies = [univers.trouver_corps(body_id) for body_id in self.corps_selectionnes]
        if self.backend is None:
            self.backend = ArrayStateBackend.depuis_corps(bodies)
        elif self.backend.body_ids != tuple(body.id for body in bodies):
            raise ValueError("SR population backend registry no longer matches selected bodies")
        forces = self.force_provider(self.backend, univers, instant)
        self.integrateur.avancer_forces_constantes(self.backend, forces, dt_s)
        self.backend.synchroniser_vers_corps(bodies)
        final = Instant(instant.seconds + float(dt_s))
        for body in bodies:
            body.etat().instant = final
        return []
