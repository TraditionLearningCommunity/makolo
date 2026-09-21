from __future__ import annotations

from datetime import datetime
from typing import Callable, Protocol

from .contracts import AttemptStrategy, ObservationMaterial
from .browser_contracts import (
    BrowserAcquisitionPolicy,
    BrowserRenderResult,
    BrowserResourceLoader,
)
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


class ObservationAcquisitionPlanPort(Protocol):
    def initial_acquisition(
        self,
        claim: ObservationClaim,
    ) -> ObservationAcquisitionPort:
        """Return the first technical strategy for this Observation."""
        ...

    def next_acquisition(
        self,
        claim: ObservationClaim,
        *,
        previous_acquisition: ObservationAcquisitionPort,
        result: AcquisitionResult,
    ) -> ObservationAcquisitionPort | None:
        """Return at most the next justified strategy, or stop."""
        ...


class BrowserRendererPort(Protocol):
    def render(
        self,
        *,
        start_url: str,
        policy: BrowserAcquisitionPolicy,
        resource_loader: BrowserResourceLoader,
        deadline_at: datetime,
        clock: Callable[[], datetime],
    ) -> BrowserRenderResult:
        """Render one public page without owning external network I/O."""
        ...
