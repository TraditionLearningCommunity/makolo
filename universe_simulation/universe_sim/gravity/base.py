"""Contracts for large-population gravitational solvers."""
from __future__ import annotations

from typing import Protocol
import numpy as np


class SolveurGravite(Protocol):
    nom: str

    def accelerations(
        self,
        positions_m: np.ndarray,
        masses_kg: np.ndarray,
        active: np.ndarray | None = None,
    ) -> np.ndarray: ...
