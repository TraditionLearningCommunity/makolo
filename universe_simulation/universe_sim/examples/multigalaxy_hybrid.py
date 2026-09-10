"""Hybrid SR/GR execution for selected black-hole encounters in the multi-galaxy scenario."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..constants import C, G, JULIAN_YEAR
from ..events import EvenementPhysique, EvenementSimulation, TypeEvenement, TypeEvenementSimulation
from ..services.horizons import rayon_horizon_externe, rayon_radial
from ..services.regime_transitions import vers_espace_temps_courbe
from ..relativistic_values import facteur_lorentz
from ..services.relativity import metrique_pour_trou_noir
from ..simulation.adaptive_geodesic import IntegrateurGeodesiqueAdaptatif
from ..simulation.dynamic_migration import DomaineObjetsRelativistesGeneraux
from ..simulation.multiregime import EvolutionGeodesiqueCorps
from ..systems import Univers
from ..values import Instant, Vecteur3
from .multigalaxy_gr_refinement import (
    materialiser_trou_noir_central,
    materialiser_vaisseau_local,
    referentiel_local_trou_noir,
)
from .multigalaxy_scenario import ProgrammePropulsionSRMultiGalaxies, ScenarioMultiGalaxies

PARSEC_M = 3.085677581491367e16


def diversifier_cibles_intergalactiques(scenario: ScenarioMultiGalaxies, *, nombre_plongees_bh: int = 8) -> np.ndarray:
    if scenario.simulation.instant_barriere.seconds != 0.0:
        raise RuntimeError("Intergalactic target diversification must happen before the run starts")
    catalogue = scenario.catalogue
    ship_slice = catalogue.tranches["ships"]
    inter = np.flatnonzero(catalogue.cibles_systemes_vaisseaux < 0)
    dive = np.zeros(len(catalogue.beta_vaisseaux), dtype=np.bool_)
    if inter.size == 0:
        return dive
    eligible = inter[(catalogue.beta_vaisseaux[inter] >= 0.8) & np.isin(catalogue.modes_mission_vaisseaux[inter], (0, 1))]
    if eligible.size < nombre_plongees_bh:
        eligible = inter[np.argsort(catalogue.beta_vaisseaux[inter])[::-1]]
    chosen = eligible[np.argsort(catalogue.beta_vaisseaux[eligible])[::-1][: max(0, nombre_plongees_bh)]]
    dive[chosen] = True
    rng = np.random.default_rng(catalogue.configuration.seed + 91_731)
    noncentral = inter[~dive[inter]]
    if noncentral.size:
        target_galaxy = catalogue.cibles_galaxies_vaisseaux[noncentral]
        theta = rng.uniform(0.0, 2.0 * np.pi, len(noncentral))
        impact = rng.uniform(0.18, 0.75, len(noncentral)) * catalogue.rayons_galaxies_m[target_galaxy]
        z = rng.normal(0.0, 0.04, len(noncentral)) * catalogue.rayons_galaxies_m[target_galaxy]
        target = catalogue.positions_galaxies_m[target_galaxy] + np.column_stack((impact * np.cos(theta), impact * np.sin(theta), z))
        start = catalogue.positions_locales_m[ship_slice][noncentral]
        direction = target - start
        direction /= np.linalg.norm(direction, axis=1)[:, None]
        speed = catalogue.beta_vaisseaux[noncentral] * C
        velocity = direction * speed[:, None]
        mass = catalogue.masses_kg[ship_slice][noncentral]
        gamma = 1.0 / np.sqrt(1.0 - catalogue.beta_vaisseaux[noncentral] ** 2)
        momentum = velocity * (gamma * mass)[:, None]
        global_rows = ship_slice.start + noncentral
        catalogue.vitesses_locales_m_s[global_rows] = velocity
        catalogue.impulsions_vaisseaux_kg_m_s[noncentral] = momentum
        scenario.vaisseaux.backend.velocities_m_s[noncentral] = velocity
        scenario.vaisseaux.backend.momenta_kg_m_s[noncentral] = momentum
    scenario.propulsion = ProgrammePropulsionSRMultiGalaxies(catalogue, scenario.duree_s)
    scenario.vaisseaux.force_provider = scenario.propulsion
    return dive


def _fractions_entree_spheres(relative_start: np.ndarray, relative_end: np.ndarray, radii_m: np.ndarray, eligible: np.ndarray) -> np.ndarray:
    delta = relative_end - relative_start
    a = np.einsum("ij,ij->i", delta, delta)
    b = 2.0 * np.einsum("ij,ij->i", relative_start, delta)
    c = np.einsum("ij,ij->i", relative_start, relative_start) - radii_m * radii_m
    disc = b * b - 4.0 * a * c
    result = np.full(len(a), np.nan, dtype=np.float64)
    already_inside = eligible & (c <= 0.0)
    result[already_inside] = 0.0
    valid = eligible & (c > 0.0) & (a > 0.0) & (disc > 0.0)
    if np.any(valid):
        root = np.sqrt(disc[valid])
        fraction = (-b[valid] - root) / (2.0 * a[valid])
        rows = np.flatnonzero(valid)
        good = (fraction > 0.0) & (fraction <= 1.0)
        result[rows[good]] = fraction[good]
    return result


@dataclass(slots=True)
class ExecutionHybrideMultiGalaxies:
    scenario: ScenarioMultiGalaxies
    plongees_bh: np.ndarray
    precision_transition_gr: float = 1e-6
    spins_bh: tuple[float, ...] | None = None
    univers_gr: Univers = field(default_factory=lambda: Univers("Sous-univers materialise GR multi-galaxies"))
    domaine_gr: DomaineObjetsRelativistesGeneraux = field(init=False)
    evenements_simulation: list[EvenementSimulation] = field(default_factory=list)
    evenements_physiques: list[EvenementPhysique] = field(default_factory=list)
    captures_horizon: set[str] = field(default_factory=set)
    migrations: dict[str, dict[str, float | int | str]] = field(default_factory=dict)
    pas_effectues: int = 0
    _trous_noirs_par_galaxie: dict[int, object] = field(default_factory=dict, init=False, repr=False)
    _referentiels_par_galaxie: dict[int, object] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if not 0 < self.precision_transition_gr < 1:
            raise ValueError("GR transition precision must lie in (0,1)")
        if self.plongees_bh.shape != (len(self.scenario.vaisseaux.backend.body_ids),):
            raise ValueError("Black-hole dive mask must have one row per SR vehicle")
        galaxy_count = self.scenario.catalogue.configuration.nombre_galaxies
        if self.spins_bh is None:
            self.spins_bh = tuple(0.0 for _ in range(galaxy_count))
        if len(self.spins_bh) != galaxy_count or any(abs(value) > 1 for value in self.spins_bh):
            raise ValueError("One dimensionless |chi|<=1 spin is required per galaxy")
        self.domaine_gr = DomaineObjetsRelativistesGeneraux("gr-black-hole-local", self.univers_gr)

    @property
    def domaines(self):
        return [self.scenario.galaxies, self.scenario.vaisseaux, self.domaine_gr]

    @property
    def instant_barriere(self) -> Instant:
        return self.scenario.simulation.instant_barriere

    @property
    def instant_courant(self) -> Instant:
        return self.instant_barriere

    @property
    def echeances_executees(self) -> int:
        return self.scenario.simulation.echeances_executees

    def _rayons_transition(self) -> np.ndarray:
        target = self.scenario.catalogue.cibles_galaxies_vaisseaux
        bh = self.scenario.catalogue.tranches["black_holes"]
        mass = self.scenario.catalogue.masses_kg[bh][target]
        return G * mass / (self.precision_transition_gr * C * C)

    def _referentiel_local(self, galaxy_index: int):
        frame = self._referentiels_par_galaxie.get(galaxy_index)
        if frame is None:
            frame = referentiel_local_trou_noir(galaxy_index)
            self._referentiels_par_galaxie[galaxy_index] = frame
        return frame

    def _trou_noir(self, galaxy_index: int, frame) -> object:
        existing = self._trous_noirs_par_galaxie.get(galaxy_index)
        if existing is not None:
            return existing
        black_hole = materialiser_trou_noir_central(self.scenario.catalogue, galaxy_index, referentiel_local=frame, spin_dimensionnel=self.spins_bh[galaxy_index])
        self.univers_gr.ajouter_corps(black_hole)
        self._trous_noirs_par_galaxie[galaxy_index] = black_hole
        return black_hole

    def _avancer_evolution_gr(self, body_id: str, start_s: float, end_s: float) -> None:
        current = float(start_s)
        while current < end_s - max(1e-9, abs(end_s) * 1e-12):
            evolution = self.domaine_gr.evolutions.get(body_id)
            if evolution is None:
                return
            body = self.univers_gr.trouver_corps(body_id)
            curved = body.etat().espace_temps
            if curved is None:
                raise RuntimeError("GR-owned vehicle lost its curved-space-time state")
            metric = evolution.integrateur.metrique
            radius = rayon_radial(metric, curved.coordonnees_m)
            horizon = rayon_horizon_externe(metric)
            if radius <= horizon:
                self.captures_horizon.add(body_id)
                self.domaine_gr.retirer_evolution(body_id)
                return
            frame_gamma = float(self.migrations[body_id].get("frame_gamma", 1.0))
            radial_local_dt = max(1e-9, 0.05 * radius / C)
            dt_group = min(end_s - current, radial_local_dt * frame_gamma)
            dt_local = dt_group / frame_gamma
            events = evolution.avancer(self.univers_gr, Instant(current), dt_local)
            for event in events:
                local_offset = event.instant.seconds - current
                event.instant = Instant(current + local_offset * frame_gamma)
            body.etat().instant = Instant(current + dt_group)
            self.evenements_physiques.extend(events)
            current += dt_group
            if any(event.type == TypeEvenement.FRANCHISSEMENT_HORIZON for event in events):
                self.captures_horizon.add(body_id)
                self.domaine_gr.retirer_evolution(body_id)
                return

    def _avancer_gr_existants(self, start_s: float, end_s: float) -> None:
        for body_id in tuple(self.domaine_gr.corps_ids):
            self._avancer_evolution_gr(body_id, start_s, end_s)

    def _materialiser_entree(self, row: int, fraction: float, start_s: float, dt_s: float, ship_pos0: np.ndarray, ship_pos1: np.ndarray, ship_p0: np.ndarray, ship_p1: np.ndarray, ship_tau0: np.ndarray, ship_tau1: np.ndarray, galaxy_pos0: np.ndarray, galaxy_pos1: np.ndarray, galaxy_vel0: np.ndarray, galaxy_vel1: np.ndarray) -> None:
        backend = self.scenario.vaisseaux.backend
        body_id = backend.body_ids[row]
        if body_id in self.migrations or body_id in self.captures_horizon:
            return
        galaxy = int(self.scenario.catalogue.cibles_galaxies_vaisseaux[row])
        event_s = start_s + fraction * dt_s
        position = ship_pos0[row] + fraction * (ship_pos1[row] - ship_pos0[row])
        momentum = ship_p0[row] + fraction * (ship_p1[row] - ship_p0[row])
        proper_time = float(ship_tau0[row] + fraction * (ship_tau1[row] - ship_tau0[row]))
        gpos = galaxy_pos0[galaxy] + fraction * (galaxy_pos1[galaxy] - galaxy_pos0[galaxy])
        gvel = galaxy_vel0[galaxy] + fraction * (galaxy_vel1[galaxy] - galaxy_vel0[galaxy])
        backend.positions_m[row] = position
        backend.momenta_kg_m_s[row] = momentum
        backend.proper_times_s[row] = proper_time
        backend.rafraichir_vitesses()
        backend.suspendre_calcul(body_id)
        frame = self._referentiel_local(galaxy)
        ship, local = materialiser_vaisseau_local(self.scenario, row, galaxy, Instant(event_s), position_groupe_m=Vecteur3.from_iterable(position), impulsion_groupe_kg_m_s=Vecteur3.from_iterable(momentum), temps_propre_s=proper_time, position_galaxie_m=Vecteur3.from_iterable(gpos), vitesse_galaxie_m_s=Vecteur3.from_iterable(gvel), referentiel_local=frame)
        black_hole = self._trou_noir(galaxy, frame)
        metric = metrique_pour_trou_noir(black_hole)
        curved = vers_espace_temps_courbe(local.etat_sr_local, metric, temps_coordonne_s=local.temps_coordonne_local_s)
        curved.instant = Instant(event_s)
        ship.etat_courant = curved
        self.univers_gr.ajouter_corps(ship)
        integrator = IntegrateurGeodesiqueAdaptatif(metric, tolerance_relative=1e-8, tolerance_absolue=max(1e-4, black_hole.rayon_reference.value * 1e-10), max_subdivisions=24)
        evolution = EvolutionGeodesiqueCorps(body_id, integrator)
        self.domaine_gr.ajouter_evolution(evolution)
        self.migrations[body_id] = {"ship_index": row, "galaxy_index": galaxy, "global_transition_time_s": event_s, "local_metric_time_s": local.temps_coordonne_local_s, "metric": type(metric).__name__, "spin": float(self.spins_bh[galaxy]), "frame_gamma": float(facteur_lorentz(Vecteur3.from_iterable(gvel)))}
        self.evenements_simulation.extend([
            EvenementSimulation(TypeEvenementSimulation.CHANGEMENT_REGIME_DYNAMIQUE, Instant(event_s), body_id, {"from": "relativiste_special", "to": "relativiste_general", "metric": type(metric).__name__}),
            EvenementSimulation(TypeEvenementSimulation.MATERIALISATION_LOD, Instant(event_s), body_id, {"target": black_hole.id, "reason": "black_hole_curvature_threshold"}),
        ])
        if event_s < start_s + dt_s:
            self._avancer_evolution_gr(body_id, event_s, start_s + dt_s)

    def avancer_segment(self, dt_s: float) -> None:
        if dt_s <= 0:
            raise ValueError("Hybrid segment duration must be positive")
        start = self.instant_barriere.seconds
        ship = self.scenario.vaisseaux.backend
        galaxy = self.scenario.galaxies.backend
        participating0 = ship.masque_evolution().copy()
        ship_pos0 = ship.positions_m.copy(); ship_p0 = ship.momenta_kg_m_s.copy(); ship_tau0 = ship.proper_times_s.copy()
        galaxy_pos0 = galaxy.positions_m.copy(); galaxy_vel0 = galaxy.velocities_m_s.copy()
        self.scenario.simulation.executer(dt_s)
        end = self.instant_barriere.seconds
        ship_pos1 = ship.positions_m.copy(); ship_p1 = ship.momenta_kg_m_s.copy(); ship_tau1 = ship.proper_times_s.copy()
        galaxy_pos1 = galaxy.positions_m.copy(); galaxy_vel1 = galaxy.velocities_m_s.copy()
        self._avancer_gr_existants(start, end)
        target = self.scenario.catalogue.cibles_galaxies_vaisseaux
        rel0 = ship_pos0 - galaxy_pos0[target]
        rel1 = ship_pos1 - galaxy_pos1[target]
        fractions = _fractions_entree_spheres(rel0, rel1, self._rayons_transition(), participating0 & self.plongees_bh)
        crossing_rows = np.flatnonzero(np.isfinite(fractions))
        for row in crossing_rows[np.argsort(fractions[crossing_rows])]:
            self._materialiser_entree(int(row), float(fractions[row]), start, dt_s, ship_pos0, ship_pos1, ship_p0, ship_p1, ship_tau0, ship_tau1, galaxy_pos0, galaxy_pos1, galaxy_vel0, galaxy_vel1)
        self.pas_effectues += 1

    def executer(self, duree_s: float | None = None, *, pas_detection_s: float | None = None, callback_barriere: Callable[["ExecutionHybrideMultiGalaxies"], None] | None = None) -> None:
        duration = self.scenario.duree_s if duree_s is None else float(duree_s)
        if duration < 0:
            raise ValueError("Duration must be non-negative")
        if pas_detection_s is None:
            pas_detection_s = self.scenario.simulation.cadences[self.scenario.vaisseaux.nom].pas_s
        step = float(pas_detection_s)
        if step <= 0:
            raise ValueError("Detection step must be positive")
        target = self.instant_barriere.seconds + duration
        if callback_barriere is not None:
            callback_barriere(self)
        while self.instant_barriere.seconds < target - max(1e-9, abs(target) * 1e-12):
            dt = min(step, target - self.instant_barriere.seconds)
            self.avancer_segment(dt)
            if callback_barriere is not None:
                callback_barriere(self)

    def resume(self) -> dict[str, object]:
        return {"coordinate_time_years": self.instant_barriere.seconds / JULIAN_YEAR, "black_hole_dive_missions": int(np.count_nonzero(self.plongees_bh)), "gr_materializations": len(self.migrations), "horizon_captures": len(self.captures_horizon), "gr_still_evolving": len(self.domaine_gr.corps_participants), "sr_still_participating": len(self.scenario.vaisseaux.corps_participants), "physical_gr_events": len(self.evenements_physiques), "simulation_transition_events": len(self.evenements_simulation), "hybrid_segments": self.pas_effectues}


def construire_execution_hybride_multi_galaxies(scenario: ScenarioMultiGalaxies, *, nombre_plongees_bh: int = 8, precision_transition_gr: float = 1e-6, spins_bh: tuple[float, ...] | None = None) -> ExecutionHybrideMultiGalaxies:
    dives = diversifier_cibles_intergalactiques(scenario, nombre_plongees_bh=nombre_plongees_bh)
    return ExecutionHybrideMultiGalaxies(scenario, dives, precision_transition_gr=precision_transition_gr, spins_bh=spins_bh)
