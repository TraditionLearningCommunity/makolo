"""Persistence adapter for simulations that mix classical, SR, 1PN and GR states."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .session import SessionPersistance


def _vector_columns(prefix: str, value: object | None, suffix: str = "") -> dict[str, float | None]:
    return {
        f"{prefix}_x{suffix}": None if value is None else getattr(value, "x", None),
        f"{prefix}_y{suffix}": None if value is None else getattr(value, "y", None),
        f"{prefix}_z{suffix}": None if value is None else getattr(value, "z", None),
    }


def _nom_integrateur(evolution: object) -> str:
    integrator = getattr(evolution, "integrateur", None)
    if integrator is None:
        return type(evolution).__name__
    return str(getattr(integrator, "nom", type(integrator).__name__))


class SessionPersistanceMultiRegime(SessionPersistance):
    """Archive a mixed-regime run without reducing relativistic states to Newtonian ones."""

    def _ecrire_etats(self, simulation: object, snapshots: list[object]) -> None:
        path = self.data_dir / "states.csv"
        fields = [
            "instant_s", "body_id", "body_name", "body_type", "kinematic_mode",
            "reference_frame", "coordinate_system",
            "position_x_m", "position_y_m", "position_z_m",
            "velocity_x_m_s", "velocity_y_m_s", "velocity_z_m_s",
            "mass_kg", "charge_c",
            "momentum_x_kg_m_s", "momentum_y_kg_m_s", "momentum_z_kg_m_s",
            "gamma_sr", "total_energy_j", "proper_time_s",
            "spacetime_ct_m", "tangent_0", "tangent_1", "tangent_2", "tangent_3",
            "affine_parameter_m", "causal_type", "coordinate_chart",
            "orientation_w", "orientation_x", "orientation_y", "orientation_z",
            "angular_velocity_x_rad_s", "angular_velocity_y_rad_s", "angular_velocity_z_rad_s",
        ]
        universe = getattr(simulation, "univers")
        body_by_id = {body.id: body for body in universe.corps_physiques}
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for snapshot in snapshots:
                for body_id, state in snapshot.etats.items():
                    body = body_by_id.get(body_id)
                    rotation = state.rotation
                    position = state.position()
                    try:
                        velocity = state.vitesse()
                    except ValueError:
                        velocity = None
                    if state.translation is not None:
                        kinematic_mode = "classical"
                    elif state.relativiste is not None:
                        kinematic_mode = "special_relativity"
                    elif state.espace_temps is not None:
                        kinematic_mode = "curved_spacetime"
                    else:
                        kinematic_mode = "none"

                    mass = None if state.massique is None else state.massique.masse.value
                    momentum = None
                    gamma_sr = None
                    total_energy = None
                    proper_time = None
                    if state.relativiste is not None:
                        momentum = state.relativiste.impulsion
                        proper_time = state.relativiste.temps_propre_s
                        if mass is not None and mass > 0:
                            gamma_sr = state.relativiste.gamma(mass)
                            total_energy = state.relativiste.energie_totale(mass)

                    curved = state.espace_temps
                    if curved is not None:
                        proper_time = curved.temps_propre_s

                    row: dict[str, Any] = {
                        "instant_s": snapshot.instant.seconds,
                        "body_id": body_id,
                        "body_name": None if body is None else body.nom,
                        "body_type": None if body is None else type(body).__name__,
                        "kinematic_mode": kinematic_mode,
                        "reference_frame": state.referentiel.nom,
                        "coordinate_system": state.systeme_coordonnees.nom,
                        "mass_kg": mass,
                        "charge_c": None if state.electrique is None else state.electrique.charge_nette.value,
                        "gamma_sr": gamma_sr,
                        "total_energy_j": total_energy,
                        "proper_time_s": proper_time,
                        "spacetime_ct_m": None if curved is None else curved.coordonnees_m[0],
                        "tangent_0": None if curved is None else curved.tangente[0],
                        "tangent_1": None if curved is None else curved.tangente[1],
                        "tangent_2": None if curved is None else curved.tangente[2],
                        "tangent_3": None if curved is None else curved.tangente[3],
                        "affine_parameter_m": None if curved is None else curved.parametre_affine_m,
                        "causal_type": None if curved is None else curved.type_causal.value,
                        "coordinate_chart": None if curved is None else curved.carte_coordonnees,
                        "orientation_w": None if rotation is None else rotation.orientation.w,
                        "orientation_x": None if rotation is None else rotation.orientation.x,
                        "orientation_y": None if rotation is None else rotation.orientation.y,
                        "orientation_z": None if rotation is None else rotation.orientation.z,
                    }
                    row.update(_vector_columns("position", position, "_m"))
                    row.update(_vector_columns("velocity", velocity, "_m_s"))
                    row.update(_vector_columns("momentum", momentum, "_kg_m_s"))
                    row.update(_vector_columns("angular_velocity", None if rotation is None else rotation.vitesse_angulaire, "_rad_s"))
                    writer.writerow(row)

    def _ecrire_metadata(
        self,
        simulation: object,
        renderer: str | None,
        rendu_path: str | None,
        diagnostic_final: dict[str, object],
        snapshot_count: int,
    ) -> None:
        epoch = simulation.horloge.epoque_reference
        modeles = [type(modele).__name__ for modele in simulation.configuration.modeles_actifs()]
        render_value = None
        if rendu_path:
            try:
                render_value = str(Path(rendu_path).resolve().relative_to(self.dossier.resolve()))
            except ValueError:
                render_value = str(Path(rendu_path))
        evolutions = [
            {
                "type": type(evolution).__name__,
                "regime": evolution.regime.value,
                "integrator": _nom_integrateur(evolution),
                "body_ids": list(evolution.corps_ids),
            }
            for evolution in getattr(simulation, "evolutions", ())
        ]
        regimes_par_corps = {
            body.id: simulation.configuration.regime_pour(body.id).value
            for body in simulation.univers.corps_physiques
        }
        metadata = {
            "schema_version": "1.1-multiregime",
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
            "scene": self.scene,
            "universe": {
                "id": simulation.univers.id,
                "name": simulation.univers.nom,
                "spacetime_model": type(simulation.univers.modele_espace_temps).__name__,
            },
            "simulation": {
                "integrator": "multi-regime",
                "evolutions": evolutions,
                "regimes_by_body": regimes_par_corps,
                "time_step_s": simulation.horloge.pas_temps.seconds,
                "steps": simulation.pas_effectues,
                "initial_instant_s": self.snapshot_initial.instant.seconds,
                "final_instant_s": simulation.horloge.instant_courant.seconds,
                "reference_epoch": {
                    "name": epoch.nom,
                    "simulation_zero_s": epoch.instant_simulation_zero.seconds,
                    "date_iso": epoch.date_iso,
                    "description": epoch.description,
                },
                "physical_models": modeles,
                "snapshots_persisted": snapshot_count,
            },
            "semantics": {
                "time_zero": "Chosen simulation epoch; not the beginning of physical time.",
                "space_origin": "Origin of the selected simulation reference frame; not an absolute center of the universe.",
                "coordinate_velocity_gr": "GR velocity columns are coordinate velocities in the state's declared coordinate chart, not locally measured invariant speeds.",
                "energy_scope": "A generic global Newtonian mechanical energy is not asserted for mixed or curved-space-time runs.",
                "gr_scope": "Built-in GR evolution uses prescribed metrics; it does not solve the Einstein field equations dynamically.",
            },
            "render": {"renderer": renderer, "path": render_value},
            "final_diagnostic": {
                "mechanical_energy_j": diagnostic_final.get("energie_mecanique"),
                "relative_energy_drift": diagnostic_final.get("derive_relative_energie"),
                "regimes": diagnostic_final.get("regimes"),
                "gamma_max_sr": diagnostic_final.get("gamma_max_sr"),
                "proper_time_min_s": diagnostic_final.get("temps_propre_min_s"),
                "proper_time_max_s": diagnostic_final.get("temps_propre_max_s"),
            },
            "extra": self.metadata_sup,
        }
        with (self.dossier / "metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, ensure_ascii=False)
