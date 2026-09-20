from __future__ import annotations

from typing import Protocol

from .contracts import AttemptStrategy, ObservationMaterial
from .runtime_contracts import AcquisitionResult, ObservationClaim


class ArtifactReaderPort(Protocol):
    def read(self, artifact_ref: str) -> bytes:
        """Return the bytes represented by an artifact reference."""
        ...


class ObservationMaterialSourcePort(Protocol):
    def get_material(self, observation_ref: str) -> ObservationMaterial:
        """Project one finalized observation for downstream interpretation."""
        ...


class ObservationAcquisitionPort(Protocol):
    strategy: AttemptStrategy

    def acquire(self, claim: ObservationClaim) -> AcquisitionResult:
        """Acquire one claimed observation using an injected strategy."""
        ...
