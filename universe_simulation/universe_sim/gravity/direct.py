"""Exact Newtonian N-body acceleration evaluated in bounded NumPy blocks."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from ..constants import G


@dataclass(frozen=True, slots=True)
class SolveurGraviteDirect:
    """Reference O(N^2) Newtonian solver without an O(N^2) memory allocation.

    Massive active rows source gravity. Active zero-mass rows are tracers: they
    feel the field but do not source it. Inactive targets receive zero
    acceleration. Softening is opt-in because it changes the physical model.
    """

    block_size: int = 1024
    softening_m: float = 0.0
    nom: str = "Direct N-body vectorise"

    def __post_init__(self) -> None:
        if self.block_size < 1:
            raise ValueError("block_size must be positive")
        if self.softening_m < 0:
            raise ValueError("softening_m must be non-negative")

    def accelerations(
        self,
        positions_m: np.ndarray,
        masses_kg: np.ndarray,
        active: np.ndarray | None = None,
    ) -> np.ndarray:
        positions = np.ascontiguousarray(np.asarray(positions_m, dtype=np.float64))
        masses = np.ascontiguousarray(np.asarray(masses_kg, dtype=np.float64))
        if positions.ndim != 2 or positions.shape[1] != 3:
            raise ValueError("positions_m must have shape (N,3)")
        n = positions.shape[0]
        if masses.shape != (n,):
            raise ValueError("masses_kg must have shape (N,)")
        if np.any(masses < 0):
            raise ValueError("Masses must be non-negative")
        if active is None:
            active_mask = np.ones(n, dtype=np.bool_)
        else:
            active_mask = np.asarray(active, dtype=np.bool_)
            if active_mask.shape != (n,):
                raise ValueError("active must have shape (N,)")

        accelerations = np.zeros((n, 3), dtype=np.float64)
        source_mask = active_mask & (masses > 0)
        source_indices = np.flatnonzero(source_mask)
        if source_indices.size == 0 or n == 0:
            return accelerations
        source_positions = positions[source_indices]
        source_masses = masses[source_indices]
        epsilon2 = self.softening_m * self.softening_m

        target_indices = np.flatnonzero(active_mask)
        for start in range(0, target_indices.size, self.block_size):
            selected = target_indices[start : start + self.block_size]
            target_positions = positions[selected]
            delta = source_positions[None, :, :] - target_positions[:, None, :]
            r2 = np.einsum("bij,bij->bi", delta, delta)

            # Self rows are identified in source-index coordinates, not by
            # position, so two distinct bodies at the same point are not hidden.
            self_pairs = selected[:, None] == source_indices[None, :]
            if self.softening_m == 0.0:
                coincident = (r2 == 0.0) & ~self_pairs
                if np.any(coincident):
                    ti, sj = np.argwhere(coincident)[0]
                    raise ValueError(
                        "Distinct massive centers coincide: "
                        f"target index {selected[ti]}, source index {source_indices[sj]}"
                    )

            denom2 = r2 + epsilon2
            # The self term has delta=0, but set its denominator to infinity to
            # make exclusion explicit and prevent 0/0 when softening is zero.
            denom2[self_pairs] = np.inf
            inv_r3 = denom2 ** -1.5
            weighted = delta * (source_masses[None, :] * inv_r3)[:, :, None]
            accelerations[selected] = G * np.sum(weighted, axis=1)

        return accelerations
