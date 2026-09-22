from __future__ import annotations

from typing import Protocol

from observer.contracts import ObservationMaterial

from .contracts import InterpretedMaterial


class InterpretedMaterialSourcePort(Protocol):
    def get_material(self, interpretation_ref: str) -> InterpretedMaterial:
        """Project one finalized interpretation for Resolver consumption."""
        ...


class InterpretationStrategyPort(Protocol):
    strategy_key: str
    strategy_version: str
    strategy_fingerprint: str

    def interpret(self, material: ObservationMaterial, artifact_reader, *, started_at, clock):
        """Transform observed material into candidates without external I/O."""
        ...
