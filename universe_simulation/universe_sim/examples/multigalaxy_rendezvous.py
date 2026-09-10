"""Pre-flight rendezvous planning against moving multi-galaxy targets.

The compact catalogue initially assigns route directions from t=0 geometry.
That is fine for short runs, but a stellar system or black-hole target can move
hundreds of parsecs during a multi-million-year flight. This module predicts
only the low-dimensional hot populations (10 galaxy centers + SR ships) before
execution and retargets reachable routes to the future target position.

No physical law is changed. The planner uses the same Newtonian galaxy
integrator and the same SR force program as the scenario. It also tightens the
galaxy cadence to the SR cadence in hybrid runs so encounter detection never
uses a galaxy center that is numerically frozen for several ship steps.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from ..constants import C
from ..simulation.array_backend import ArrayStateBackend
from ..simulation.multirate import CadenceEvolution
from ..simulation.population import IntegrateurPopulationNewtonienneTableau
from ..simulation.sr_population import IntegrateurPopulationSRTableau
from ..values import Instant
from .multigalaxy_scenario import ProgrammePropulsionSRMultiGalaxies, ScenarioMultiGalaxies


@dataclass(frozen=True, slots=True)
class PlanRendezvousMultiGalaxies:
    temps_arrivee_s: np.ndarray
    cibles_predites_m: np.ndarray
    atteignable: np.ndarray
    plongee_bh: np.ndarray

    @property
    def nombre_atteignables(self) -> int:
        return int(np.count_nonzero(self.atteignable))


def _copier_backend(source: ArrayStateBackend) -> ArrayStateBackend:
    return ArrayStateBackend(
        source.body_ids,
        source.positions_m.copy(),
        source.velocities_m_s.copy(),
        source.momenta_kg_m_s.copy(),
        source.masses_kg.copy(),
        source.charges_c.copy(),
        source.proper_times_s.copy(),
        source.active.copy(),
        source.regime_codes.copy(),
        None if source.participating is None else source.participating.copy(),
    )


def planifier_rendezvous_mobiles(
    scenario: ScenarioMultiGalaxies,
    *,
    plongees_bh: np.ndarray | None = None,
) -> PlanRendezvousMultiGalaxies:
    """Retarget reachable missions to moving galaxy/system centers.

    The trajectory *speed* history is predicted using a copied SR backend and
    the current mission force provider. Direction does not affect the scalar
    path length because the current mission program is collinear. Galaxy
    centers are predicted using a copied Newtonian backend.

    Rows that cannot reach their target within the requested coordinate-time
    horizon are left unchanged. Black-hole-dive rows target the predicted
    galaxy center exactly. System missions target the predicted stellar-system
    center. Other intergalactic missions keep a deterministic non-central
    impact offset in the target-galaxy frame.
    """
    if scenario.simulation.instant_barriere.seconds != 0.0:
        raise RuntimeError("Mobile rendezvous planning must happen before the run starts")

    catalogue = scenario.catalogue
    ships = scenario.vaisseaux.backend
    galaxies = scenario.galaxies.backend
    n = len(ships.body_ids)
    dive = np.zeros(n, dtype=np.bool_) if plongees_bh is None else np.asarray(plongees_bh, dtype=np.bool_).copy()
    if dive.shape != (n,):
        raise ValueError("Black-hole dive mask must have one row per SR vehicle")

    ship_step = scenario.simulation.cadences[scenario.vaisseaux.nom].pas_s
    # Ten galaxy centers are cheap to evolve; keep their committed state at the
    # same cadence used by encounter detection to avoid stale multi-rate centers.
    scenario.simulation.cadences[scenario.galaxies.nom] = CadenceEvolution(
        scenario.galaxies.nom,
        ship_step,
    )

    temp_gal = _copier_backend(galaxies)
    temp_ship = _copier_backend(ships)
    gal_integrator = IntegrateurPopulationNewtonienneTableau()
    sr_integrator = IntegrateurPopulationSRTableau()

    start = ships.positions_m.copy()
    target_galaxy = catalogue.cibles_galaxies_vaisseaux.astype(np.int64)
    target_system = catalogue.cibles_systemes_vaisseaux.astype(np.int64)

    local_offset = np.zeros((n, 3), dtype=np.float64)
    system_rows = target_system >= 0
    if np.any(system_rows):
        local_offset[system_rows] = catalogue.positions_systemes_dans_galaxie_m[target_system[system_rows]]

    # Reproduce the deterministic non-central galaxy impact convention for
    # intergalactic rows, but apply it around the *future* galaxy center.
    inter = np.flatnonzero(target_system < 0)
    noncentral = inter[~dive[inter]]
    if noncentral.size:
        rng = np.random.default_rng(catalogue.configuration.seed + 91_731)
        theta = rng.uniform(0.0, 2.0 * np.pi, len(noncentral))
        radii = catalogue.rayons_galaxies_m[target_galaxy[noncentral]]
        impact = rng.uniform(0.18, 0.75, len(noncentral)) * radii
        z = rng.normal(0.0, 0.04, len(noncentral)) * radii
        local_offset[noncentral] = np.column_stack(
            (impact * np.cos(theta), impact * np.sin(theta), z)
        )

    arrival = np.full(n, np.nan, dtype=np.float64)
    predicted_target = np.zeros((n, 3), dtype=np.float64)
    reachable = np.zeros(n, dtype=np.bool_)
    cumulative = np.zeros(n, dtype=np.float64)

    target0 = temp_gal.positions_m[target_galaxy] + local_offset
    residual_previous = np.linalg.norm(target0 - start, axis=1)
    time_s = 0.0
    duration_s = float(scenario.duree_s)

    while time_s < duration_s - max(1e-9, duration_s * 1e-12):
        dt = min(ship_step, duration_s - time_s)
        previous_galaxy_positions = temp_gal.positions_m.copy()
        previous_ship_positions = temp_ship.positions_m.copy()

        gal_integrator.avancer(temp_gal, dt)
        forces = scenario.propulsion(temp_ship, Instant(time_s))
        sr_integrator.avancer_forces_constantes(temp_ship, forces, dt)
        cumulative += np.linalg.norm(temp_ship.positions_m - previous_ship_positions, axis=1)

        target1 = temp_gal.positions_m[target_galaxy] + local_offset
        residual = np.linalg.norm(target1 - start, axis=1) - cumulative
        crossing = (~reachable) & (residual <= 0.0)
        if np.any(crossing):
            rows = np.flatnonzero(crossing)
            denom = residual_previous[rows] - residual[rows]
            fraction = np.ones(len(rows), dtype=np.float64)
            valid = np.abs(denom) > 1e-30
            fraction[valid] = np.clip(residual_previous[rows][valid] / denom[valid], 0.0, 1.0)
            g0 = previous_galaxy_positions[target_galaxy[rows]] + local_offset[rows]
            g1 = target1[rows]
            predicted_target[rows] = g0 + fraction[:, None] * (g1 - g0)
            arrival[rows] = time_s + fraction * dt
            reachable[rows] = True

        residual_previous = residual
        time_s += dt

    rows = np.flatnonzero(reachable)
    if rows.size:
        direction = predicted_target[rows] - start[rows]
        norm = np.linalg.norm(direction, axis=1)
        valid = norm > 0.0
        rows = rows[valid]
        direction = direction[valid] / norm[valid, None]
        speed = catalogue.beta_vaisseaux[rows] * C
        velocity = direction * speed[:, None]
        mass = ships.masses_kg[rows]
        gamma = 1.0 / np.sqrt(1.0 - catalogue.beta_vaisseaux[rows] ** 2)
        momentum = velocity * (gamma * mass)[:, None]

        ship_slice = catalogue.tranches["ships"]
        global_rows = ship_slice.start + rows
        catalogue.vitesses_locales_m_s[global_rows] = velocity
        catalogue.impulsions_vaisseaux_kg_m_s[rows] = momentum
        ships.velocities_m_s[rows] = velocity
        ships.momenta_kg_m_s[rows] = momentum

    # The thrust provider caches the direction vector, therefore rebuild it
    # after retargeting but before the first physical step.
    scenario.propulsion = ProgrammePropulsionSRMultiGalaxies(catalogue, scenario.duree_s)
    scenario.vaisseaux.force_provider = scenario.propulsion

    return PlanRendezvousMultiGalaxies(arrival, predicted_target, reachable, dive)
