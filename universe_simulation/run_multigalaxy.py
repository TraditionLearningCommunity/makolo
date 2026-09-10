#!/usr/bin/env python3
"""Run and persist the deterministic Makolo multi-galaxy scenario."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np

from universe_sim.examples.multigalaxy_analysis import analyser_navigation_multi_galaxies
from universe_sim.examples.multigalaxy_hybrid import construire_execution_hybride_multi_galaxies
from universe_sim.examples.multigalaxy_scenario import construire_scenario_multi_galaxies
from universe_sim.persistence import ConfigurationSessionGrandeEchelle, SessionPersistanceGrandeEchelleMultiDomaine


def _jsonable(value):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def sauvegarder_catalogue(catalogue, root: Path) -> None:
    directory = root / "catalogue"
    directory.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        directory / "catalogue_compact.npz",
        positions_galaxies_m=catalogue.positions_galaxies_m,
        vitesses_galaxies_m_s=catalogue.vitesses_galaxies_m_s,
        masses_galaxies_kg=catalogue.masses_galaxies_kg,
        rayons_galaxies_m=catalogue.rayons_galaxies_m,
        galaxie_par_systeme=catalogue.galaxie_par_systeme,
        positions_systemes_dans_galaxie_m=catalogue.positions_systemes_dans_galaxie_m,
        vitesses_systemes_dans_galaxie_m_s=catalogue.vitesses_systemes_dans_galaxie_m_s,
        types_entites=catalogue.types_entites,
        types_cadres=catalogue.types_cadres,
        indices_cadres=catalogue.indices_cadres,
        indices_parents=catalogue.indices_parents,
        positions_locales_m=catalogue.positions_locales_m,
        vitesses_locales_m_s=catalogue.vitesses_locales_m_s,
        masses_kg=catalogue.masses_kg,
        rayons_m=catalogue.rayons_m,
        niveaux_activite=catalogue.niveaux_activite,
        impulsions_vaisseaux_kg_m_s=catalogue.impulsions_vaisseaux_kg_m_s,
        beta_vaisseaux=catalogue.beta_vaisseaux,
        origines_systemes_vaisseaux=catalogue.origines_systemes_vaisseaux,
        cibles_systemes_vaisseaux=catalogue.cibles_systemes_vaisseaux,
        cibles_galaxies_vaisseaux=catalogue.cibles_galaxies_vaisseaux,
        modes_mission_vaisseaux=catalogue.modes_mission_vaisseaux,
        delta_rapidite_vaisseaux=catalogue.delta_rapidite_vaisseaux,
        fraction_acceleration_vaisseaux=catalogue.fraction_acceleration_vaisseaux,
        fraction_deceleration_vaisseaux=catalogue.fraction_deceleration_vaisseaux,
    )
    metadata = {
        "scale": catalogue.configuration.nom,
        "seed": catalogue.configuration.seed,
        "galaxies": catalogue.configuration.nombre_galaxies,
        "stellar_systems": catalogue.configuration.nombre_systemes,
        "entities": catalogue.nombre_entites,
        "counts": catalogue.compteurs(),
        "morphologies": catalogue.morphologies_galaxies,
        "array_memory_bytes": catalogue.memoire_tableaux_octets(),
        "slices": {name: [sl.start, sl.stop] for name, sl in catalogue.tranches.items()},
        "coordinate_semantics": {
            "galaxies": "group inertial frame",
            "stellar_catalogue": "local host-galaxy / host-system frames",
            "ships": "group inertial frame until explicit GR migration",
        },
    }
    (directory / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=_jsonable), encoding="utf-8")


def _capture_states(root: Path, scenario, hybrid=None) -> None:
    states = root / "final_states"
    states.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        states / "galaxies_final.npz",
        body_ids=np.asarray(scenario.galaxies.backend.body_ids, dtype=np.str_),
        positions_m=scenario.galaxies.backend.positions_m,
        velocities_m_s=scenario.galaxies.backend.velocities_m_s,
        masses_kg=scenario.galaxies.backend.masses_kg,
    )
    ships = scenario.vaisseaux.backend
    np.savez_compressed(
        states / "ships_final.npz",
        body_ids=np.asarray(ships.body_ids, dtype=np.str_),
        positions_m=ships.positions_m,
        momenta_kg_m_s=ships.momenta_kg_m_s,
        velocities_m_s=ships.velocities_m_s,
        proper_times_s=ships.proper_times_s,
        physically_active=ships.active,
        participating=ships.participating,
    )
    if hybrid is not None:
        captured = []
        for body_id in sorted(hybrid.captures_horizon):
            body = hybrid.univers_gr.trouver_corps(body_id)
            curved = body.etat().espace_temps
            captured.append({
                "body_id": body_id,
                "instant_s": body.etat().instant.seconds,
                "coordinates_m": curved.coordonnees_m if curved is not None else None,
                "tangent": curved.tangente if curved is not None else None,
                "proper_time_s": None if curved is None else curved.temps_propre_s,
            })
        _write_json(states / "captured_at_horizon.json", captured)


def run(args) -> tuple[Path, Path | None]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.output_dir) / f"{timestamp}_{args.scale}_{int(args.years)}y"
    root.mkdir(parents=True, exist_ok=False)
    scenario = construire_scenario_multi_galaxies(args.scale, args.years)

    execution = None
    if args.hybrid:
        spins = None
        if args.kerr_demo:
            pattern = (0.0, 0.25, 0.5, 0.75, 0.9, -0.4, 0.6, 0.2, -0.8, 0.95)
            spins = pattern[: scenario.catalogue.configuration.nombre_galaxies]
        execution = construire_execution_hybride_multi_galaxies(
            scenario,
            nombre_plongees_bh=args.bh_dives,
            precision_transition_gr=args.gr_precision,
            spins_bh=spins,
        )

    # Persist only after hybrid target preparation so the saved catalogue is
    # exactly the set of initial conditions used by the run.
    sauvegarder_catalogue(scenario.catalogue, root)

    if execution is not None:
        persistence = SessionPersistanceGrandeEchelleMultiDomaine(
            ConfigurationSessionGrandeEchelle(root / "run", frames_par_chunk=args.frames_per_chunk)
        )
        sample_interval = scenario.duree_s / max(1, args.samples - 1)
        next_sample = 0.0
        seen_sim = 0
        seen_phys = 0

        def persist_at_barrier(sim):
            nonlocal next_sample, seen_sim, seen_phys
            t = sim.instant_barriere.seconds
            tolerance = max(1e-6, abs(scenario.duree_s) * 1e-12)
            if t + tolerance < next_sample and t + tolerance < scenario.duree_s:
                return
            events = sim.evenements_simulation[seen_sim:] + sim.evenements_physiques[seen_phys:]
            persistence.ajouter_frame(sim, events)
            seen_sim = len(sim.evenements_simulation)
            seen_phys = len(sim.evenements_physiques)
            while next_sample <= t + tolerance:
                next_sample += sample_interval

        execution.executer(callback_barriere=persist_at_barrier)
        persistence.finaliser(execution)
        _write_json(root / "migrations.json", execution.migrations)
        _write_json(root / "hybrid_summary.json", execution.resume())
        _capture_states(root, scenario, execution)
    else:
        persistence = SessionPersistanceGrandeEchelleMultiDomaine(
            ConfigurationSessionGrandeEchelle(root / "run", frames_par_chunk=args.frames_per_chunk)
        )
        persistence.ajouter_frame(scenario.simulation)
        scenario.executer()
        persistence.ajouter_frame(scenario.simulation)
        persistence.finaliser(scenario.simulation)
        _capture_states(root, scenario)

    base_summary = scenario.resume()
    navigation = analyser_navigation_multi_galaxies(scenario, precision_gr=args.gr_precision)
    _write_json(root / "summary.json", {"simulation": base_summary, "navigation": navigation.resume(), "hybrid": args.hybrid})
    _write_json(root / "parameters.json", {
        "scale": args.scale, "years": args.years, "hybrid": args.hybrid,
        "bh_dives": args.bh_dives, "gr_precision": args.gr_precision,
        "kerr_demo": args.kerr_demo, "samples": args.samples,
        "frames_per_chunk": args.frames_per_chunk,
    })
    archive = Path(shutil.make_archive(str(root), "zip", root_dir=root)) if args.zip else None
    return root, archive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", choices=("mini", "10k", "100k", "500k"), default="mini")
    parser.add_argument("--years", type=float, default=10_000.0)
    parser.add_argument("--hybrid", action="store_true", help="Enable selected SR -> GR black-hole transitions")
    parser.add_argument("--bh-dives", type=int, default=8)
    parser.add_argument("--gr-precision", type=float, default=1e-6)
    parser.add_argument("--kerr-demo", action="store_true", help="Use deterministic non-zero spins on some central black holes")
    parser.add_argument("--samples", type=int, default=64, help="Persistence samples across the full run")
    parser.add_argument("--frames-per-chunk", type=int, default=4)
    parser.add_argument("--output-dir", default="simulation_outputs/multigalaxy")
    parser.add_argument("--zip", action="store_true")
    return parser


if __name__ == "__main__":
    options = build_parser().parse_args()
    output, archive = run(options)
    print(f"Output: {output}")
    if archive is not None:
        print(f"Archive: {archive}")
