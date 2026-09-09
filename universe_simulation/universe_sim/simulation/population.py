"""Vectorized evolution of large classical Newtonian populations."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..events import EvenementPhysique
from ..gravity import SolveurGravite, SolveurGraviteDirect
from ..regimes import RegimeDynamique
from ..systems import Univers
from ..values import Instant
from .array_backend import ArrayStateBackend, _REGIME_TO_CODE


@dataclass(slots=True)
class IntegrateurPopulationNewtonienneTableau:
    """Velocity-Verlet integrator operating directly on a classical array backend."""

    solveur: SolveurGravite = field(default_factory=SolveurGraviteDirect)
    nom: str = "Velocity-Verlet population vectorise"

    def avancer(self, backend: ArrayStateBackend, dt_s: float) -> None:
        dt = float(dt_s)
        if dt <= 0:
            raise ValueError("Time step must be positive")
        classical_code = _REGIME_TO_CODE[RegimeDynamique.CLASSIQUE]
        if np.any(backend.regime_codes != classical_code):
            raise ValueError("Newtonian population integrator accepts only classical array rows")

        # Velocity is a primary classical state for zero-mass tracers and is
        # reconstructed from momentum for massive rows.
        backend.rafraichir_vitesses()
        active = backend.active
        if not np.any(active):
            return

        a0 = self.solveur.accelerations(backend.positions_m, backend.masses_kg, active)
        dt2 = dt * dt
        backend.positions_m[active] += backend.velocities_m_s[active] * dt + 0.5 * a0[active] * dt2
        a1 = self.solveur.accelerations(backend.positions_m, backend.masses_kg, active)
        backend.velocities_m_s[active] += 0.5 * (a0[active] + a1[active]) * dt

        massive = active & (backend.masses_kg > 0)
        backend.momenta_kg_m_s[massive] = backend.velocities_m_s[massive] * backend.masses_kg[massive, None]
        tracers = active & (backend.masses_kg == 0)
        backend.momenta_kg_m_s[tracers] = 0.0


@dataclass(slots=True)
class EvolutionPopulationClassiqueTableau:
    """Multi-regime adapter for a large classical population stored as arrays."""

    corps_selectionnes: tuple[str, ...]
    integrateur: IntegrateurPopulationNewtonienneTableau = field(default_factory=IntegrateurPopulationNewtonienneTableau)
    backend: ArrayStateBackend | None = None
    regime: RegimeDynamique = field(default=RegimeDynamique.CLASSIQUE, init=False)

    @property
    def corps_ids(self) -> tuple[str, ...]:
        return self.corps_selectionnes

    def _corps(self, univers: Univers):
        return [univers.trouver_corps(body_id) for body_id in self.corps_selectionnes]

    def avancer(self, univers: Univers, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        bodies = self._corps(univers)
        if self.backend is None:
            self.backend = ArrayStateBackend.depuis_corps(bodies)
        elif self.backend.body_ids != tuple(body.id for body in bodies):
            raise ValueError("Population backend registry no longer matches selected bodies")

        self.integrateur.avancer(self.backend, dt_s)
        self.backend.synchroniser_vers_corps(bodies)
        final = Instant(instant.seconds + float(dt_s))
        for body in bodies:
            body.etat().instant = final
        return []
