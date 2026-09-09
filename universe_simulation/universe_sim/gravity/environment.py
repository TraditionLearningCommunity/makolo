"""Far-field gravitational environment queries for regime/LOD decisions.

This module estimates Newtonian potential as a weak-field diagnostic. It does
not apply ``F=ma`` to relativistic vehicles. When the estimated curvature is no
longer negligible at the requested accuracy, the caller should migrate the
vehicle to an appropriate GR path.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..constants import G
from ..regime_selector import DiagnosticRegime, SeuilsSelectionRegime, diagnostiquer_regime
from ..simulation.array_backend import ArrayStateBackend
from ..simulation.hierarchy import EtatAgregeSysteme, RegistreHierarchiqueUnivers
from ..values import Vecteur3


@dataclass(frozen=True, slots=True)
class SourcesPotentielAgregees:
    systeme_ids: tuple[str, ...]
    positions_m: np.ndarray
    masses_kg: np.ndarray
    rayons_couverture_m: np.ndarray

    def __post_init__(self) -> None:
        n = len(self.systeme_ids)
        positions = np.ascontiguousarray(np.asarray(self.positions_m, dtype=np.float64))
        masses = np.ascontiguousarray(np.asarray(self.masses_kg, dtype=np.float64))
        radii = np.ascontiguousarray(np.asarray(self.rayons_couverture_m, dtype=np.float64))
        if positions.shape != (n, 3):
            raise ValueError("Aggregate positions must have shape (N,3)")
        if masses.shape != (n,) or radii.shape != (n,):
            raise ValueError("Aggregate masses/radii must have shape (N,)")
        if np.any(masses < 0) or np.any(radii < 0):
            raise ValueError("Aggregate masses and radii must be non-negative")
        object.__setattr__(self, "positions_m", positions)
        object.__setattr__(self, "masses_kg", masses)
        object.__setattr__(self, "rayons_couverture_m", radii)

    @classmethod
    def depuis_agregats(cls, agregats: tuple[EtatAgregeSysteme, ...]) -> "SourcesPotentielAgregees":
        return cls(
            tuple(state.systeme_id for state in agregats),
            np.asarray([state.barycentre_m.as_tuple() for state in agregats], dtype=np.float64).reshape((-1, 3)),
            np.asarray([state.masse_kg for state in agregats], dtype=np.float64),
            np.asarray([state.rayon_couverture_m for state in agregats], dtype=np.float64),
        )

    @classmethod
    def depuis_registre(cls, registre: RegistreHierarchiqueUnivers) -> "SourcesPotentielAgregees":
        return cls.depuis_agregats(registre.frontiere_agregee())


@dataclass(frozen=True, slots=True)
class EvaluationPotentielLointain:
    potentiel_j_kg: np.ndarray
    dans_couverture_source: np.ndarray
    source_proche_index: np.ndarray


def evaluer_potentiel_lointain(
    cibles_m: np.ndarray,
    sources: SourcesPotentielAgregees,
    block_size: int = 2048,
) -> EvaluationPotentielLointain:
    """Evaluate aggregate Newtonian potential at arbitrary target positions.

    The source coverage radius regularizes the monopole inside an aggregate and
    separately flags that the target has entered material that may need to be
    opened to a finer LOD. This potential is a regime-selection proxy, not a GR
    metric and not a force law for SR vehicles.
    """
    targets = np.ascontiguousarray(np.asarray(cibles_m, dtype=np.float64))
    if targets.ndim != 2 or targets.shape[1] != 3:
        raise ValueError("cibles_m must have shape (M,3)")
    if block_size < 1:
        raise ValueError("block_size must be positive")
    m = targets.shape[0]
    potential = np.zeros(m, dtype=np.float64)
    inside = np.zeros(m, dtype=np.bool_)
    nearest = np.full(m, -1, dtype=np.int64)
    if len(sources.systeme_ids) == 0:
        return EvaluationPotentielLointain(potential, inside, nearest)

    positive = sources.masses_kg > 0
    source_positions = sources.positions_m[positive]
    source_masses = sources.masses_kg[positive]
    source_radii = sources.rayons_couverture_m[positive]
    original_indices = np.flatnonzero(positive)
    if source_masses.size == 0:
        return EvaluationPotentielLointain(potential, inside, nearest)

    for start in range(0, m, block_size):
        stop = min(m, start + block_size)
        delta = targets[start:stop, None, :] - source_positions[None, :, :]
        distance = np.linalg.norm(delta, axis=2)
        local_nearest = np.argmin(distance, axis=1)
        nearest[start:stop] = original_indices[local_nearest]
        local_inside = distance <= source_radii[None, :]
        inside[start:stop] = np.any(local_inside, axis=1)
        # An aggregate monopole is not physically resolved inside its coverage.
        # Clamp only for the diagnostic value; the inside flag tells the LOD
        # manager that the source should be opened if more fidelity is needed.
        effective_radius = np.maximum(distance, source_radii[None, :])
        zero_radius_zero_distance = effective_radius == 0.0
        if np.any(zero_radius_zero_distance):
            effective_radius[zero_radius_zero_distance] = np.finfo(np.float64).tiny
        potential[start:stop] = -G * np.sum(source_masses[None, :] / effective_radius, axis=1)
    return EvaluationPotentielLointain(potential, inside, nearest)


@dataclass(frozen=True, slots=True)
class DiagnosticPopulationSR:
    diagnostics: tuple[DiagnosticRegime, ...]
    potentiel: EvaluationPotentielLointain

    def indices_regime(self, regime: object) -> np.ndarray:
        return np.asarray([i for i, diagnostic in enumerate(self.diagnostics) if diagnostic.regime == regime], dtype=np.int64)


def diagnostiquer_population_sr(
    backend: ArrayStateBackend,
    sources: SourcesPotentielAgregees,
    seuils: SeuilsSelectionRegime | None = None,
    block_size: int = 2048,
) -> DiagnosticPopulationSR:
    """Diagnose the physical regime of each SR row from speed and far potential."""
    backend.rafraichir_vitesses()
    potential = evaluer_potentiel_lointain(backend.positions_m, sources, block_size)
    diagnostics = tuple(
        diagnostiquer_regime(
            Vecteur3.from_iterable(backend.velocities_m_s[i]),
            float(potential.potentiel_j_kg[i]),
            seuils,
        )
        for i in range(len(backend.body_ids))
    )
    return DiagnosticPopulationSR(diagnostics, potential)
