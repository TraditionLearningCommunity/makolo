from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .contracts import AttemptStrategy
from .runtime_contracts import AcquisitionResult, ObservationClaim


@dataclass
class FakeAcquisition:
    """Deterministic test adapter. Never wired by the operational worker."""

    result_factory: Callable[[ObservationClaim], AcquisitionResult]
    strategy: AttemptStrategy = AttemptStrategy.DIRECT_HTTP
    calls: list[ObservationClaim] | None = None

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def acquire(self, claim: ObservationClaim) -> AcquisitionResult:
        self.calls.append(claim)
        return self.result_factory(claim)
