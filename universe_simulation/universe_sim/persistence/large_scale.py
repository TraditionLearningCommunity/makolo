"""Chunked compressed persistence for large array-backed simulation runs."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Iterable

import numpy as np

from ..simulation.array_backend import ArrayStateBackend


@dataclass(frozen=True, slots=True)
class ConfigurationPersistanceGrandeEchelle:
    dossier: str | Path
    frames_par_chunk: int = 8
    stocker_charges_dynamiques: bool = False

    def __post_init__(self) -> None:
        if self.frames_par_chunk < 1:
            raise ValueError("frames_par_chunk must be positive")


@dataclass(slots=True)
class EcrivainEtatsChunkesNPZ:
    """Append array states and flush bounded frame chunks to compressed NPZ files.

    Positions, canonical momenta, masses, activity and regime codes are stored
    every sampled frame. Velocities are stored only for zero-mass tracers,
    because massive classical and SR velocities are derivable from momentum.
    """

    configuration: ConfigurationPersistanceGrandeEchelle
    body_ids: tuple[str, ...] | None = None
    _catalogue_initialise: bool = field(default=False, init=False, repr=False)
    _times: list[float] = field(default_factory=list, init=False, repr=False)
    _positions: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _momenta: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _masses: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _proper_times: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _active: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _regimes: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _charges: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _tracer_velocities: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _tracer_indices: np.ndarray | None = field(default=None, init=False, repr=False)
    _chunks: list[dict[str, object]] = field(default_factory=list, init=False, repr=False)
    _next_chunk: int = field(default=0, init=False, repr=False)
    root: Path = field(init=False)
    states_dir: Path = field(init=False)
    catalogue_dir: Path = field(init=False)
    events_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.root = Path(self.configuration.dossier)
        self.states_dir = self.root / "states" / "chunks"
        self.catalogue_dir = self.root / "catalogue"
        self.events_dir = self.root / "events"
        for path in (self.states_dir, self.catalogue_dir, self.events_dir):
            path.mkdir(parents=True, exist_ok=True)

    def _initialiser_catalogue(self, backend: ArrayStateBackend) -> None:
        if self.body_ids is not None and self.body_ids != backend.body_ids:
            raise ValueError("Configured body ids do not match backend registry")
        self.body_ids = backend.body_ids
        self._tracer_indices = np.flatnonzero(backend.masses_kg == 0).astype(np.int64)
        np.savez_compressed(
            self.catalogue_dir / "bodies.npz",
            body_ids=np.asarray(backend.body_ids, dtype=np.str_),
            masses_initial_kg=backend.masses_kg,
            charges_initial_c=backend.charges_c,
            regimes_initial=backend.regime_codes,
            tracer_indices=self._tracer_indices,
        )
        self._catalogue_initialise = True

    def ajouter_frame(self, instant_s: float, backend: ArrayStateBackend) -> None:
        if not self._catalogue_initialise:
            self._initialiser_catalogue(backend)
        elif backend.body_ids != self.body_ids:
            raise ValueError("Backend registry changed during chunked persistence")
        assert self._tracer_indices is not None
        self._times.append(float(instant_s))
        self._positions.append(backend.positions_m.copy())
        self._momenta.append(backend.momenta_kg_m_s.copy())
        self._masses.append(backend.masses_kg.copy())
        self._proper_times.append(backend.proper_times_s.copy())
        self._active.append(backend.active.copy())
        self._regimes.append(backend.regime_codes.copy())
        if self.configuration.stocker_charges_dynamiques:
            self._charges.append(backend.charges_c.copy())
        self._tracer_velocities.append(backend.velocities_m_s[self._tracer_indices].copy())
        if len(self._times) >= self.configuration.frames_par_chunk:
            self._vider_chunk()

    def _vider_chunk(self) -> None:
        if not self._times:
            return
        filename = f"states_{self._next_chunk:06d}.npz"
        path = self.states_dir / filename
        payload = {
            "times_s": np.asarray(self._times, dtype=np.float64),
            "positions_m": np.stack(self._positions),
            "momenta_kg_m_s": np.stack(self._momenta),
            "masses_kg": np.stack(self._masses),
            "proper_times_s": np.stack(self._proper_times),
            "active": np.stack(self._active),
            "regime_codes": np.stack(self._regimes),
            "tracer_velocities_m_s": np.stack(self._tracer_velocities),
        }
        if self.configuration.stocker_charges_dynamiques:
            payload["charges_c"] = np.stack(self._charges)
        np.savez_compressed(path, **payload)
        self._chunks.append(
            {
                "file": str(path.relative_to(self.root)),
                "frames": len(self._times),
                "first_time_s": self._times[0],
                "last_time_s": self._times[-1],
            }
        )
        self._next_chunk += 1
        self._times.clear(); self._positions.clear(); self._momenta.clear(); self._masses.clear()
        self._proper_times.clear(); self._active.clear(); self._regimes.clear(); self._charges.clear(); self._tracer_velocities.clear()

    def finaliser(self) -> Path:
        self._vider_chunk()
        schema = {
            "schema_version": "1.0",
            "format": "chunked-npz",
            "coordinate_state": "positions + canonical momenta",
            "massive_velocity": "derived from momentum and regime",
            "zero_mass_tracer_velocity": "stored explicitly",
            "body_count": 0 if self.body_ids is None else len(self.body_ids),
            "chunks": self._chunks,
        }
        with (self.root / "states" / "index.json").open("w", encoding="utf-8") as handle:
            json.dump(schema, handle, indent=2, ensure_ascii=False)
        return self.root


@dataclass(slots=True)
class EcrivainEvenementsJSONL:
    dossier: str | Path
    path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.path = Path(self.dossier) / "events" / "physical_events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def ajouter(self, evenements: Iterable[object]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            for event in evenements:
                position = getattr(event, "position", None)
                record = {
                    "id": getattr(event, "id", None),
                    "type": getattr(getattr(event, "type", None), "value", str(getattr(event, "type", ""))),
                    "instant_s": getattr(getattr(event, "instant", None), "seconds", None),
                    "participants_ids": list(getattr(event, "participants_ids", ())),
                    "position_m": None if position is None else [position.x, position.y, position.z],
                    "details": getattr(event, "details", {}),
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
