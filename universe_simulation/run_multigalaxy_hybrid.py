#!/usr/bin/env python3
"""Run the multi-galaxy hybrid scenario with moving-target rendezvous planning."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np

from run_multigalaxy import _capture_states, _write_json, sauvegarder_catalogue
from universe_sim.examples.multigalaxy_hybrid import construire_execution_hybride_multi_galaxies
from universe_sim.examples.multigalaxy_rendezvous import planifier_rendezvous_mobiles
from universe_sim.examples.multigalaxy_scenario import construire_scenario_multi_galaxies
from universe_sim.persistence import ConfigurationSessionGrandeEchelle, SessionPersistanceGrandeEchelleMultiDomaine


def run(args) -> tuple[Path, Path | None]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.output_dir) / f"{timestamp}_{args.scale}_{int(args.years)}y_hybrid"
    root.mkdir(parents=True, exist_ok=False)

    scenario = construire_scenario_multi_galaxies(args.scale, args.years)
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
    rendezvous = planifier_rendezvous_mobiles(
        scenario,
        plongees_bh=execution.plongees_bh,
    )

    # Save only after all route retargeting so persisted initial conditions are
    # exactly those used by the physical execution.
    sauvegarder_catalogue(scenario.catalogue, root)
    np.savez_compressed(
        root / "catalogue" / "mobile_rendezvous.npz",
        arrival_time_s=rendezvous.temps_arrivee_s,
        predicted_targets_m=rendezvous.cibles_predites_m,
        reachable=rendezvous.atteignable,
        black_hole_dive=rendezvous.plongee_bh,
    )

    persistence = SessionPersistanceGrandeEchelleMultiDomaine(
        ConfigurationSessionGrandeEchelle(
            root / "run",
            frames_par_chunk=args.frames_per_chunk,
        )
    )
    sample_interval = scenario.duree_s / max(1, args.samples - 1)
    next_sample = 0.0
    seen_sim = 0
    seen_phys = 0

    def persist_at_barrier(sim) -> None:
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
    _write_json(
        root / "rendezvous_summary.json",
        {
            "reachable_routes": rendezvous.nombre_atteignables,
            "total_routes": len(rendezvous.atteignable),
            "black_hole_dive_routes": int(np.count_nonzero(rendezvous.plongee_bh)),
            "galaxy_and_ship_cadence_s": scenario.simulation.cadences[scenario.vaisseaux.nom].pas_s,
            "semantics": "Targets are predicted in coordinate time using copied Newtonian galaxy and SR vehicle dynamics before the run.",
        },
    )
    _capture_states(root, scenario, execution)

    archive = Path(shutil.make_archive(str(root), "zip", root_dir=root)) if args.zip else None
    return root, archive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", choices=("mini", "10k", "100k", "500k"), default="mini")
    parser.add_argument("--years", type=float, default=10_000.0)
    parser.add_argument("--bh-dives", type=int, default=8)
    parser.add_argument("--gr-precision", type=float, default=1e-6)
    parser.add_argument("--kerr-demo", action="store_true")
    parser.add_argument("--samples", type=int, default=64)
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
