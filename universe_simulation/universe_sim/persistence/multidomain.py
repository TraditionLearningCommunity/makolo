"""Persistence session for several authoritative large-scale array domains."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Iterable

from ..simulation.array_backend import ArrayStateBackend
from .large_scale import (
    ConfigurationPersistanceGrandeEchelle,
    EcrivainEtatsChunkesNPZ,
    EcrivainEvenementsJSONL,
)


def _slug_domaine(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return result or "domain"


@dataclass(frozen=True, slots=True)
class ConfigurationSessionGrandeEchelle:
    dossier: str | Path
    frames_par_chunk: int = 8
    stocker_charges_dynamiques: bool = False

    def __post_init__(self) -> None:
        if self.frames_par_chunk < 1:
            raise ValueError("frames_par_chunk must be positive")


@dataclass(slots=True)
class SessionPersistanceGrandeEchelleMultiDomaine:
    """Persist multiple hot array domains without synchronizing Python objects."""

    configuration: ConfigurationSessionGrandeEchelle
    _writers: dict[str, EcrivainEtatsChunkesNPZ] = field(default_factory=dict, init=False, repr=False)
    _domain_info: dict[str, dict[str, object]] = field(default_factory=dict, init=False, repr=False)
    _frames: int = field(default=0, init=False, repr=False)
    _initial_time_s: float | None = field(default=None, init=False, repr=False)
    _last_time_s: float | None = field(default=None, init=False, repr=False)
    _event_writer: EcrivainEvenementsJSONL = field(init=False, repr=False)
    root: Path = field(init=False)

    def __post_init__(self) -> None:
        self.root = Path(self.configuration.dossier)
        self.root.mkdir(parents=True, exist_ok=True)
        self._event_writer = EcrivainEvenementsJSONL(self.root)

    def _initialiser_domaines(self, simulation: object) -> None:
        names: set[str] = set()
        slugs: set[str] = set()
        for domain in getattr(simulation, "domaines", ()):
            name = str(getattr(domain, "nom", ""))
            if not name or name in names:
                raise ValueError("Large-scale persistence requires unique non-empty domain names")
            backend = getattr(domain, "backend", None)
            if not isinstance(backend, ArrayStateBackend):
                raise TypeError(f"Domain {name} has no array backend to persist")
            slug = _slug_domaine(name)
            if slug in slugs:
                raise ValueError("Domain names collide after persistence slug normalization")
            names.add(name)
            slugs.add(slug)
            domain_root = self.root / "domains" / slug
            writer = EcrivainEtatsChunkesNPZ(
                ConfigurationPersistanceGrandeEchelle(
                    domain_root,
                    frames_par_chunk=self.configuration.frames_par_chunk,
                    stocker_charges_dynamiques=self.configuration.stocker_charges_dynamiques,
                )
            )
            self._writers[name] = writer
            regime = getattr(getattr(domain, "regime", None), "value", str(getattr(domain, "regime", "")))
            self._domain_info[name] = {
                "name": name,
                "slug": slug,
                "path": str(domain_root.relative_to(self.root)),
                "regime": regime,
                "body_count": len(backend.body_ids),
            }

    def ajouter_frame(self, simulation: object, evenements: Iterable[object] = ()) -> None:
        if not self._writers:
            self._initialiser_domaines(simulation)
        domains = {str(domain.nom): domain for domain in getattr(simulation, "domaines", ())}
        if set(domains) != set(self._writers):
            raise ValueError("Simulation domain registry changed during persistence")
        instant = getattr(simulation, "instant_courant", None)
        if instant is None:
            raise TypeError("Large-scale simulation must expose instant_courant")
        time_s = float(instant.seconds)
        if self._last_time_s is not None and time_s < self._last_time_s:
            raise ValueError("Persistence frames must be monotonic in coordinate time")
        if self._initial_time_s is None:
            self._initial_time_s = time_s
        for name, writer in self._writers.items():
            backend = getattr(domains[name], "backend", None)
            if not isinstance(backend, ArrayStateBackend):
                raise TypeError(f"Domain {name} lost its array backend")
            writer.ajouter_frame(time_s, backend)
        self._event_writer.ajouter(evenements)
        self._last_time_s = time_s
        self._frames += 1

    def finaliser(self, simulation: object) -> Path:
        for writer in self._writers.values():
            writer.finaliser()
        metadata = {
            "schema_version": "1.0",
            "format": "multi-domain-chunked-npz",
            "initial_time_s": self._initial_time_s,
            "final_time_s": self._last_time_s,
            "frames": self._frames,
            "steps": int(getattr(simulation, "pas_effectues", 0)),
            "domains": [self._domain_info[name] for name in sorted(self._domain_info)],
            "semantics": {
                "hot_state": "Array backends are authoritative between explicit object synchronization barriers.",
                "coordinate_time": "All persisted domain frames share the same coordinate-time sample.",
                "sr_momentum": "Special-relativistic velocity is derived from canonical momentum and rest mass.",
            },
        }
        with (self.root / "metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, ensure_ascii=False)
        return self.root
