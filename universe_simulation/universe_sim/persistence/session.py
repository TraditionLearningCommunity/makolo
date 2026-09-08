"""Persistence of simulation runs, deliberately separated from physical models."""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..simulation import Simulation, Snapshot


@dataclass(frozen=True, slots=True)
class ConfigurationPersistance:
    save_simulation: bool = False
    dossier_racine: str | Path = "simulation_outputs"
    nom_execution: str | None = None
    sauvegarder_corps: bool = True
    sauvegarder_etats: bool = True
    sauvegarder_systemes: bool = True
    sauvegarder_diagnostics: bool = True


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    return value.strip("-") or "simulation"


def _vector_columns(prefix: str, value: object | None, unit_suffix: str = "") -> dict[str, float | None]:
    return {
        f"{prefix}_x{unit_suffix}": None if value is None else getattr(value, "x", None),
        f"{prefix}_y{unit_suffix}": None if value is None else getattr(value, "y", None),
        f"{prefix}_z{unit_suffix}": None if value is None else getattr(value, "z", None),
    }


class SessionPersistance:
    """Archive one execution into a self-contained, ordered directory."""

    def __init__(
        self,
        configuration: ConfigurationPersistance,
        dossier: Path,
        scene: str | None,
        diagnostic_initial: dict[str, object],
        snapshot_initial: Snapshot,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.configuration = configuration
        self.dossier = dossier
        self.scene = scene
        self.diagnostic_initial = diagnostic_initial
        self.snapshot_initial = snapshot_initial
        self.metadata_sup = dict(metadata or {})
        self.cree_a = datetime.now(timezone.utc)
        self.data_dir = dossier / "data"
        self.images_dir = dossier / "images"
        self.videos_dir = dossier / "videos"
        self.interactive_dir = dossier / "interactive"
        self.logs_dir = dossier / "logs"
        for path in (self.data_dir, self.images_dir, self.videos_dir, self.interactive_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def demarrer(
        cls,
        simulation: Simulation,
        configuration: ConfigurationPersistance,
        scene: str | None = None,
        diagnostic_initial: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> "SessionPersistance":
        if not configuration.save_simulation:
            raise ValueError("Persistence session requested while save_simulation=False")
        racine = Path(configuration.dossier_racine)
        racine.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = configuration.nom_execution or scene or simulation.univers.nom
        nom = f"{horodatage}_{_slug(base)}_{uuid4().hex[:6]}"
        dossier = racine / nom
        dossier.mkdir(parents=True, exist_ok=False)
        diagnostic = diagnostic_initial if diagnostic_initial is not None else simulation.diagnostic()
        return cls(
            configuration,
            dossier,
            scene,
            diagnostic,
            Snapshot.capturer(simulation.univers, simulation.horloge.instant_courant),
            metadata,
        )

    def chemin_rendu(self, renderer: str, requested: str | None = None) -> str | None:
        if requested:
            path = Path(requested)
            if path.is_absolute() or path.parent != Path("."):
                path.parent.mkdir(parents=True, exist_ok=True)
                return str(path)
            return str(self._dossier_media(path.suffix) / path.name)
        if renderer == "plotly":
            return str(self.interactive_dir / "animation_3d.html")
        if renderer == "pyvista":
            return str(self.videos_dir / "animation_3d.mp4")
        if renderer == "2d":
            return str(self.videos_dir / "animation_2d.gif")
        return None

    def _dossier_media(self, suffix: str) -> Path:
        suffix = suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
            return self.images_dir
        if suffix in {".mp4", ".gif", ".mov", ".webm"}:
            return self.videos_dir
        if suffix in {".html", ".htm"}:
            return self.interactive_dir
        return self.dossier

    def finaliser(
        self,
        simulation: Simulation,
        sequence: object | None = None,
        renderer: str | None = None,
        rendu_path: str | None = None,
        diagnostic_final: dict[str, object] | None = None,
    ) -> Path:
        final = Snapshot.capturer(simulation.univers, simulation.horloge.instant_courant)
        snapshots = self._snapshots_ordonnes(simulation, final)
        diagnostic_final = diagnostic_final if diagnostic_final is not None else simulation.diagnostic()

        if self.configuration.sauvegarder_corps:
            self._ecrire_corps(simulation)
        if self.configuration.sauvegarder_etats:
            self._ecrire_etats(simulation, snapshots)
        if self.configuration.sauvegarder_systemes:
            self._ecrire_systemes(simulation)
        if self.configuration.sauvegarder_diagnostics:
            self._ecrire_diagnostics(simulation, diagnostic_final)
        if sequence is not None:
            self._ecrire_frames_visuelles(sequence)

        self._ecrire_metadata(simulation, renderer, rendu_path, diagnostic_final, len(snapshots))
        self._ecrire_manifest()
        return self.dossier

    def _snapshots_ordonnes(self, simulation: Simulation, final: Snapshot) -> list[Snapshot]:
        par_instant: dict[float, Snapshot] = {self.snapshot_initial.instant.seconds: self.snapshot_initial}
        for snapshot in simulation.snapshots:
            par_instant[snapshot.instant.seconds] = snapshot
        par_instant[final.instant.seconds] = final
        return [par_instant[t] for t in sorted(par_instant)]

    def _ecrire_corps(self, simulation: Simulation) -> None:
        path = self.data_dir / "bodies.csv"
        fields = ["id", "name", "type", "active", "shape", "radius_m", "mass_kg", "charge_c"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for body in simulation.univers.corps_physiques:
                writer.writerow(
                    {
                        "id": body.id,
                        "name": body.nom,
                        "type": type(body).__name__,
                        "active": body.actif,
                        "shape": body.forme_reference,
                        "radius_m": None if body.rayon_reference is None else body.rayon_reference.value,
                        "mass_kg": None if body.etat().massique is None else body.masse().value,
                        "charge_c": None if body.etat().electrique is None else body.charge().value,
                    }
                )

    def _ecrire_etats(self, simulation: Simulation, snapshots: list[Snapshot]) -> None:
        path = self.data_dir / "states.csv"
        fields = [
            "instant_s", "body_id", "body_name", "body_type", "reference_frame", "coordinate_system",
            "position_x_m", "position_y_m", "position_z_m", "velocity_x_m_s", "velocity_y_m_s", "velocity_z_m_s",
            "mass_kg", "charge_c", "orientation_w", "orientation_x", "orientation_y", "orientation_z",
            "angular_velocity_x_rad_s", "angular_velocity_y_rad_s", "angular_velocity_z_rad_s",
        ]
        body_by_id = {body.id: body for body in simulation.univers.corps_physiques}
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for snapshot in snapshots:
                for body_id, state in snapshot.etats.items():
                    body = body_by_id.get(body_id)
                    translation = state.translation
                    rotation = state.rotation
                    row: dict[str, Any] = {
                        "instant_s": snapshot.instant.seconds,
                        "body_id": body_id,
                        "body_name": None if body is None else body.nom,
                        "body_type": None if body is None else type(body).__name__,
                        "reference_frame": state.referentiel.nom,
                        "coordinate_system": state.systeme_coordonnees.nom,
                        "mass_kg": None if state.massique is None else state.massique.masse.value,
                        "charge_c": None if state.electrique is None else state.electrique.charge_nette.value,
                        "orientation_w": None if rotation is None else rotation.orientation.w,
                        "orientation_x": None if rotation is None else rotation.orientation.x,
                        "orientation_y": None if rotation is None else rotation.orientation.y,
                        "orientation_z": None if rotation is None else rotation.orientation.z,
                    }
                    row.update(_vector_columns("position", None if translation is None else translation.position, "_m"))
                    row.update(_vector_columns("velocity", None if translation is None else translation.vitesse, "_m_s"))
                    row.update(_vector_columns("angular_velocity", None if rotation is None else rotation.vitesse_angulaire, "_rad_s"))
                    writer.writerow(row)

    def _ecrire_systemes(self, simulation: Simulation) -> None:
        path = self.data_dir / "systems.csv"
        fields = ["system_id", "system_name", "system_type", "relation", "member_id", "member_name", "subsystem_id", "subsystem_name"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for systeme in simulation.univers.systemes_physiques:
                if not systeme.membres and not systeme.sous_systemes:
                    writer.writerow({"system_id": systeme.id, "system_name": systeme.nom, "system_type": type(systeme).__name__, "relation": "system"})
                for member in systeme.membres:
                    writer.writerow(
                        {
                            "system_id": systeme.id,
                            "system_name": systeme.nom,
                            "system_type": type(systeme).__name__,
                            "relation": "member",
                            "member_id": member.id,
                            "member_name": member.nom,
                        }
                    )
                for subsystem in systeme.sous_systemes:
                    writer.writerow(
                        {
                            "system_id": systeme.id,
                            "system_name": systeme.nom,
                            "system_type": type(systeme).__name__,
                            "relation": "subsystem",
                            "subsystem_id": subsystem.id,
                            "subsystem_name": subsystem.nom,
                        }
                    )

    def _ecrire_diagnostics(self, simulation: Simulation, diagnostic_final: dict[str, object]) -> None:
        path = self.data_dir / "diagnostics.csv"
        fields = [
            "phase", "instant_s", "mechanical_energy_j", "relative_energy_drift",
            "momentum_x", "momentum_y", "momentum_z", "angular_momentum_x", "angular_momentum_y", "angular_momentum_z",
        ]
        diagnostics = (
            ("initial", self.snapshot_initial.instant.seconds, self.diagnostic_initial),
            ("final", simulation.horloge.instant_courant.seconds, diagnostic_final),
        )
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for phase, instant, diagnostic in diagnostics:
                p = diagnostic.get("quantite_mouvement")
                l = diagnostic.get("moment_cinetique")
                writer.writerow(
                    {
                        "phase": phase,
                        "instant_s": instant,
                        "mechanical_energy_j": diagnostic.get("energie_mecanique"),
                        "relative_energy_drift": diagnostic.get("derive_relative_energie"),
                        "momentum_x": getattr(p, "x", None),
                        "momentum_y": getattr(p, "y", None),
                        "momentum_z": getattr(p, "z", None),
                        "angular_momentum_x": getattr(l, "x", None),
                        "angular_momentum_y": getattr(l, "y", None),
                        "angular_momentum_z": getattr(l, "z", None),
                    }
                )

    def _ecrire_frames_visuelles(self, sequence: object) -> None:
        frames = getattr(sequence, "frames", ())
        corps = {c.id: c for c in getattr(sequence, "corps", ())}
        path = self.data_dir / "visual_frames.csv"
        fields = ["frame", "instant_s", "body_id", "body_name", "x_m", "y_m", "z_m"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for index, frame in enumerate(frames):
                for body_id, position in frame.positions.items():
                    body = corps.get(body_id)
                    writer.writerow(
                        {
                            "frame": index,
                            "instant_s": frame.instant_s,
                            "body_id": body_id,
                            "body_name": None if body is None else body.nom,
                            "x_m": position.x,
                            "y_m": position.y,
                            "z_m": position.z,
                        }
                    )

    def _ecrire_metadata(
        self,
        simulation: Simulation,
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
        metadata = {
            "schema_version": "1.0",
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
            "scene": self.scene,
            "universe": {
                "id": simulation.univers.id,
                "name": simulation.univers.nom,
                "spacetime_model": type(simulation.univers.modele_espace_temps).__name__,
            },
            "simulation": {
                "integrator": simulation.integrateur.nom,
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
            },
            "render": {"renderer": renderer, "path": render_value},
            "final_diagnostic": {
                "mechanical_energy_j": diagnostic_final.get("energie_mecanique"),
                "relative_energy_drift": diagnostic_final.get("derive_relative_energie"),
            },
            "extra": self.metadata_sup,
        }
        with (self.dossier / "metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, ensure_ascii=False)

    def _ecrire_manifest(self) -> None:
        files = []
        for path in sorted(self.dossier.rglob("*")):
            if path.is_file() and path.name != "manifest.json":
                files.append(str(path.relative_to(self.dossier)))
        with (self.dossier / "manifest.json").open("w", encoding="utf-8") as handle:
            json.dump({"files": files}, handle, indent=2, ensure_ascii=False)
