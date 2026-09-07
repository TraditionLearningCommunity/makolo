from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Protocol


class PointsTargetPolicy(Protocol):
    version: str

    def target_points(self, cumulative_impact: Decimal) -> int:
        """Return the cumulative finite point-pool target for one accrual."""


@dataclass(frozen=True, slots=True)
class SimulationPolicyV0:
    """Illustrative policy used only for simulation and contract tests.

    These parameters are intentionally *not* a production tariff. Production
    RecognitionPolicy versions may change the curve without repricing ledger
    entries that were already granted. Decimal arithmetic keeps simulations
    deterministic across runtimes.
    """

    version: str = "simulation-v0"
    scale: Decimal = Decimal("140")
    exponent: Decimal = Decimal("0.90")

    def target_points(self, cumulative_impact: Decimal) -> int:
        cumulative_impact = max(Decimal("0"), Decimal(cumulative_impact))
        if cumulative_impact == 0:
            return 0
        with localcontext() as ctx:
            ctx.prec = 40
            raw = self.scale * (cumulative_impact ** self.exponent)
            return max(0, int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
