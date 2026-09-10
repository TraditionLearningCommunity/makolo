"""Post-run hierarchical encounter analysis for multi-galaxy trajectories."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from ..constants import C, G
from .multigalaxy_scenario import ScenarioMultiGalaxies

PARSEC_M = 3.085677581491367e16


def _closest_fraction_and_distance(relative_start: np.ndarray, relative_end: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    delta = relative_end - relative_start
    denom = np.einsum("ij,ij->i", delta, delta)
    fraction = np.divide(
        -np.einsum("ij,ij->i", relative_start, delta),
        denom,
        out=np.zeros(len(relative_start), dtype=np.float64),
        where=denom > 0,
    )
    fraction = np.clip(fraction, 0.0, 1.0)
    closest = relative_start + fraction[:, None] * delta
    return fraction, np.linalg.norm(closest, axis=1)


@dataclass(frozen=True, slots=True)
class AnalyseNavigationMultiGalaxies:
    distance_min_galaxie_m: np.ndarray
    fraction_plus_proche_galaxie: np.ndarray
    entre_dans_galaxie_cible: np.ndarray
    distance_min_systeme_m: np.ndarray
    approche_systeme_cible: np.ndarray
    rayon_transition_gr_m: np.ndarray
    candidat_gr: np.ndarray
    distance_min_bh_en_rs: np.ndarray

    def resume(self) -> dict[str, object]:
        finite_system = np.isfinite(self.distance_min_systeme_m)
        return {
            "target_galaxy_entries": int(np.count_nonzero(self.entre_dans_galaxie_cible)),
            "target_system_close_passes": int(np.count_nonzero(self.approche_systeme_cible)),
            "gr_candidates": int(np.count_nonzero(self.candidat_gr)),
            "closest_target_galaxy_pc": float(np.min(self.distance_min_galaxie_m) / PARSEC_M),
            "closest_target_system_pc": (
                None if not np.any(finite_system) else float(np.min(self.distance_min_systeme_m[finite_system]) / PARSEC_M)
            ),
            "closest_black_hole_rs": float(np.min(self.distance_min_bh_en_rs)),
        }


def analyser_navigation_multi_galaxies(
    scenario: ScenarioMultiGalaxies,
    *,
    precision_gr: float = 1e-6,
    rayon_ouverture_systeme_pc: float = 1.0,
) -> AnalyseNavigationMultiGalaxies:
    if not 0 < precision_gr < 1:
        raise ValueError("GR precision threshold must lie in (0,1)")
    if rayon_ouverture_systeme_pc <= 0:
        raise ValueError("System opening radius must be positive")
    if not scenario.simulation.simultanes(max(1e-6, abs(scenario.duree_s) * 1e-12)):
        raise RuntimeError("Navigation analysis requires a synchronized coordinate-time barrier")

    catalogue = scenario.catalogue
    ships = scenario.vaisseaux.backend
    start_ship = catalogue.positions_locales_m[catalogue.tranches["ships"]]
    end_ship = ships.positions_m
    target_galaxy = catalogue.cibles_galaxies_vaisseaux
    start_galaxy = catalogue.positions_galaxies_m[target_galaxy]
    end_galaxy = scenario.galaxies.backend.positions_m[target_galaxy]
    fraction_galaxy, distance_galaxy = _closest_fraction_and_distance(
        start_ship - start_galaxy,
        end_ship - end_galaxy,
    )
    galaxy_radius = catalogue.rayons_galaxies_m[target_galaxy]
    enters_galaxy = distance_galaxy <= galaxy_radius

    black_holes = catalogue.tranches["black_holes"]
    bh_mass = catalogue.masses_kg[black_holes][target_galaxy]
    schwarzschild_radius = 2.0 * G * bh_mass / (C * C)
    transition_radius = G * bh_mass / (precision_gr * C * C)
    gr_candidate = distance_galaxy <= transition_radius
    distance_rs = distance_galaxy / schwarzschild_radius

    target_system = catalogue.cibles_systemes_vaisseaux
    distance_system = np.full(len(target_system), np.inf, dtype=np.float64)
    valid_system = target_system >= 0
    if np.any(valid_system):
        system_index = target_system[valid_system]
        system_galaxy = catalogue.galaxie_par_systeme[system_index]
        system_start = (
            catalogue.positions_galaxies_m[system_galaxy]
            + catalogue.positions_systemes_dans_galaxie_m[system_index]
        )
        # Coarse LOD prediction only: systems are analytic catalogue entries and
        # their local barycentric velocity is advanced linearly across the run.
        system_end = (
            scenario.galaxies.backend.positions_m[system_galaxy]
            + catalogue.positions_systemes_dans_galaxie_m[system_index]
            + catalogue.vitesses_systemes_dans_galaxie_m_s[system_index] * scenario.duree_s
        )
        _, local_distance = _closest_fraction_and_distance(
            start_ship[valid_system] - system_start,
            end_ship[valid_system] - system_end,
        )
        distance_system[valid_system] = local_distance
    opens_system = distance_system <= rayon_ouverture_systeme_pc * PARSEC_M

    return AnalyseNavigationMultiGalaxies(
        distance_galaxy,
        fraction_galaxy,
        enters_galaxy,
        distance_system,
        opens_system,
        transition_radius,
        gr_candidate,
        distance_rs,
    )
