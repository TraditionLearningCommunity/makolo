"""Persistence session for mixed large-scale array and materialized GR domains."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Iterable

from ..regimes import RegimeDynamique
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
            raise ValueError("frames_per_chunk must be positive")


@dataclass(slots=True)
class EcrivainLignesUniversGRJSONL:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def ajouter_frame(self, instant_s: float, domaine: object) -> None:
        universe = getattr(domaine, "univers", None)
        if universe is None:
            raise TypeError("Materialized GR domain must expose its universe")
        with self.path.open("a", encoding="utf-8") as handle:
            for body_id in getattr(domaine, "corps_participants", ()):
                body = universe.trouver_corps(body_id)
                state = body.etat()
                curved = state.espace_temps
                if curved is None:
                    raise ValueError(f"Materialized GR body {body_id} has no curved-space-time state")
                record = {
                    "instant_s": float(instant_s),
                    "body_id": body_id,
                    "body_name": body.nom,
                    "ct_m": curved.coordonnees_m[0],
                    "x_m": curved.coordonnees_m[1],
                    "y_m": curved.coordonnees_m[2],
                    "z_m": curved.coordonnees_m[3],
                    "tangent_0": curved.tangente[0],
                    "tangent_1": curved.tangente[1],
                    "tangent_2": curved.tangente[2],
                    "tangent_3": curved.tangente[3],
                    "affine_parameter_m": curved.parametre_affine_m,
                    "proper_time_s": curved.temps_propre_s,
                    "causal_type": curved.type_causal.value,
                    "coordinate_chart": curved.carte_coordonnees,
                    "physically_active": bool(body.actif),
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def finaliser(self) -> None:
        return None


@dataclass(slots=True)
class SessionPersistanceGrandeEchelleMultiDomaine:
    """Persist hot arrays and small materialized GR domains in one run."""

    configuration: ConfigurationSessionGrandeEchelle
    _array_writers: dict[str, EcrivainEtatsChunkesNPZ] = field(default_factory=dict, init=False, repr=False)
    _gr_writers: dict[str, EcrivainLignesUniversGRJSONL] = field(default_factory=dict, init=False, repr=False)
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
            slug = _slug_domaine(name)
            if slug in slugs:
                raise ValueError("Domain names collide after persistence slug normalization")
            names.add(name)
            slugs.add(slug)
            domain_root = self.root / "domains" / slug
            regime = getattr(getattr(domain, "regime", None), "value", str(getattr(domain, "regime", "")))
            backend = getattr(domain, "backend", None)
            if isinstance(backend, ArrayStateBackend):
                writer = EcrivainEtatsChunkesNPZ(
                    ConfigurationPersistanceGrandeEchelle(
                        domain_root,
                        frames_par_chunk=self.configuration.frames_par_chunk,
                        stocker_charges_dynamiques=self.configuration.stocker_charges_dynamiques,
                    )
                )
                self._array_writers[name] = writer
                self._domain_info[name] = {
                    "name": name,
                    "slug": slug,
                    "path": str(domain_root.relative_to(self.root)),
                    "regime": regime,
                    "storage": "chunked-npz",
                    "body_count": len(backend.body_ids),
                    "dynamic_participation": True,
                }
            elif getattr(domain, "regime", None) == RegimeDynamique.RELATIVISTE_GENERAL and getattr(domain, "univers", None) is not None:
                path = domain_root / "states" / "worldlines.jsonl"
                self._gr_writers[name] = EcrivainLignesUniversGRJSONL(path)
                self._domain_info[name] = {
                    "name": name,
                    "slug": slug,
                    "path": str(domain_root.relative_to(self.root)),
                    "regime": regime,
                    "storage": "gr-worldlines-jsonl",
                    "body_count": "dynamic",
                    "dynamic_participation": True,
                }
            else:
                raise TypeError(f"Domain {name} has no supported persistence representation")

    def _domain_names(self) -> set[str]:
        return set(self._array_writers) | set(self._gr_writers)

    @staticmethod
    def _instant_simulation(simulation: object):
        instant = getattr(simulation, "instant_courant", None)
        if instant is not None:
            return instant
        try:
            return simulation.instant_barriere
        except (AttributeError, RuntimeError) as exc:
            raise TypeError("Large-scale persistence requires a common coordinate-time barrier") from exc

    def ajouter_frame(self, simulation: object, evenements: Iterable[object] = ()) -> None:
        if not self._domain_info:
            self._initialiser_domaines(simulation)
        domains = {str(domain.nom): domain for domain in getattr(simulation, "domaines", ())}
        if set(domains) != self._domain_names():
            raise ValueError("Simulation domain registry changed during persistence")
        instant = self._instant_simulation(simulation)
        time_s = float(instant.seconds)
        if self._last_time_s is not None and time_s < self._last_time_s:
            raise ValueError("Persistence frames must be monotonic in coordinate time")
        if self._initial_time_s is None:
            self._initial_time_s = time_s
        for name, writer in self._array_writers.items():
            backend = getattr(domains[name], "backend", None)
            if not isinstance(backend, ArrayStateBackend):
                raise TypeError(f"Domain {name} lost its array backend")
            writer.ajouter_frame(time_s, backend)
        for name, writer in self._gr_writers.items():
            writer.ajouter_frame(time_s, domains[name])
        self._event_writer.ajouter(evenements)
        self._last_time_s = time_s
        self._frames += 1

    def finaliser(self, simulation: object) -> Path:
        for writer in self._array_writers.values():
            writer.finaliser()
        for writer in self._gr_writers.values():
            writer.finaliser()
        metadata = {
            "schema_version": "1.1",
            "format": "hybrid-multi-domain",
            "initial_time_s": self._initial_time_s,
            "final_time_s": self._last_time_s,
            "frames": self._frames,
            "steps": int(getattr(simulation, "pas_effectues", 0)),
            "deadlines": int(getattr(simulation, "echeances_executees", 0)),
            "domains": [self._domain_info[name] for name in sorted(self._domain_info)],
            "semantics": {
                "hot_state": "Array backends are authoritative between explicit object synchronization barriers.",
                "coordinate_time": "All persisted domains are sampled only at a common coordinate-time barrier.",
                "sr_momentum": "Special-relativistic velocity is derived from canonical momentum and rest mass.",
                "gr_worldline": "Materialized GR bodies persist four-coordinates and tangents in their explicit chart.",
            },
        }
        with (self.root / "metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, ensure_ascii=False)
        return self.root
