"""Optional Numba-compiled traversal for the Barnes-Hut octree."""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

from ..constants import G
from .barnes_hut import SolveurGraviteBarnesHut

try:  # optional performance dependency
    from numba import njit, prange
except ImportError:  # pragma: no cover - exercised on installs without performance extra
    njit = None
    prange = range


NUMBA_DISPONIBLE = njit is not None


if NUMBA_DISPONIBLE:
    @njit(cache=True, parallel=True)
    def _parcourir_octree_compile_avec_feuilles(
        positions,
        masses,
        active,
        node_centres,
        node_half,
        node_masses,
        node_com,
        children,
        leaf_offsets,
        leaf_counts,
        leaf_sources,
        root,
        theta,
        epsilon2,
        stack_capacity,
        target_block_size,
        target_start,
        target_end,
    ):
        n_targets = target_end - target_start
        out = np.zeros((n_targets, 3), dtype=np.float64)
        n_blocks = (n_targets + target_block_size - 1) // target_block_size
        for block in prange(n_blocks):
            stack = np.empty(stack_capacity, dtype=np.int64)
            start_local = block * target_block_size
            end_local = min(n_targets, start_local + target_block_size)
            for local_target in range(start_local, end_local):
                target = target_start + local_target
                if not active[target]:
                    continue
                tx = positions[target, 0]
                ty = positions[target, 1]
                tz = positions[target, 2]
                stack[0] = root
                sp = 1
                ax = 0.0
                ay = 0.0
                az = 0.0
                while sp > 0:
                    sp -= 1
                    node = stack[sp]
                    count = leaf_counts[node]
                    if count > 0:
                        start = leaf_offsets[node]
                        for local in range(count):
                            source = leaf_sources[start + local]
                            if source == target:
                                continue
                            dx = positions[source, 0] - tx
                            dy = positions[source, 1] - ty
                            dz = positions[source, 2] - tz
                            r2 = dx * dx + dy * dy + dz * dz + epsilon2
                            inv_r3 = 1.0 / (r2 * math.sqrt(r2))
                            factor = G * masses[source] * inv_r3
                            ax += factor * dx
                            ay += factor * dy
                            az += factor * dz
                        continue

                    dx = node_com[node, 0] - tx
                    dy = node_com[node, 1] - ty
                    dz = node_com[node, 2] - tz
                    distance2 = dx * dx + dy * dy + dz * dz
                    contains = (
                        abs(tx - node_centres[node, 0]) <= node_half[node]
                        and abs(ty - node_centres[node, 1]) <= node_half[node]
                        and abs(tz - node_centres[node, 2]) <= node_half[node]
                    )
                    distance = math.sqrt(distance2)
                    size = 2.0 * node_half[node]
                    if (not contains) and distance > 0.0 and size / distance < theta:
                        denom2 = distance2 + epsilon2
                        inv_r3 = 1.0 / (denom2 * math.sqrt(denom2))
                        factor = G * node_masses[node] * inv_r3
                        ax += factor * dx
                        ay += factor * dy
                        az += factor * dz
                    else:
                        for child_slot in range(8):
                            child = children[node, child_slot]
                            if child >= 0:
                                stack[sp] = child
                                sp += 1
                out[local_target, 0] = ax
                out[local_target, 1] = ay
                out[local_target, 2] = az
        return out
else:
    _parcourir_octree_compile_avec_feuilles = None


@dataclass(frozen=True, slots=True)
class SolveurGraviteBarnesHutCompile:
    """Barnes-Hut with Python tree construction and block-parallel Numba traversal."""

    theta: float = 0.6
    leaf_capacity: int = 16
    max_depth: int = 64
    softening_m: float = 0.0
    target_block_size: int = 512
    target_batch_size: int = 250_000
    nom: str = "Barnes-Hut 3D compile (Numba)"

    def __post_init__(self) -> None:
        SolveurGraviteBarnesHut(self.theta, self.leaf_capacity, self.max_depth, self.softening_m)
        if self.target_block_size < 1:
            raise ValueError("target_block_size must be positive")
        if self.target_batch_size < 1:
            raise ValueError("target_batch_size must be positive")

    def accelerations(self, positions_m, masses_kg, active=None):
        if not NUMBA_DISPONIBLE:
            raise RuntimeError("Numba acceleration is unavailable; install the 'performance' extra")
        positions = np.ascontiguousarray(np.asarray(positions_m, dtype=np.float64))
        masses = np.ascontiguousarray(np.asarray(masses_kg, dtype=np.float64))
        if positions.ndim != 2 or positions.shape[1] != 3:
            raise ValueError("positions_m must have shape (N,3)")
        n = positions.shape[0]
        if masses.shape != (n,):
            raise ValueError("masses_kg must have shape (N,)")
        if np.any(masses < 0):
            raise ValueError("Masses must be non-negative")
        active_mask = np.ones(n, dtype=np.bool_) if active is None else np.ascontiguousarray(np.asarray(active, dtype=np.bool_))
        if active_mask.shape != (n,):
            raise ValueError("active must have shape (N,)")
        source_indices = np.flatnonzero(active_mask & (masses > 0))
        if source_indices.size == 0:
            return np.zeros((n, 3), dtype=np.float64)
        source_positions = positions[source_indices]
        if self.softening_m == 0.0 and source_indices.size > 1:
            if np.unique(source_positions, axis=0).shape[0] != source_indices.size:
                raise ValueError("Distinct massive centers coincide")

        reference = SolveurGraviteBarnesHut(self.theta, self.leaf_capacity, self.max_depth, self.softening_m)
        nodes, root = reference._construire_octree(positions, masses, source_indices)
        node_count = len(nodes)
        centres = np.empty((node_count, 3), dtype=np.float64)
        half = np.empty(node_count, dtype=np.float64)
        node_masses = np.empty(node_count, dtype=np.float64)
        com = np.empty((node_count, 3), dtype=np.float64)
        children = np.full((node_count, 8), -1, dtype=np.int64)
        leaf_offsets = np.full(node_count, -1, dtype=np.int64)
        leaf_counts = np.zeros(node_count, dtype=np.int64)
        packed_sources: list[int] = []
        for i, node in enumerate(nodes):
            centres[i] = node.centre_m
            half[i] = node.demi_taille_m
            node_masses[i] = node.masse_kg
            com[i] = node.centre_masse_m
            for slot, child in enumerate(node.enfants):
                children[i, slot] = child
            if node.indices_sources is not None:
                leaf_offsets[i] = len(packed_sources)
                leaf_counts[i] = len(node.indices_sources)
                packed_sources.extend(int(v) for v in node.indices_sources)
        leaf_sources = np.asarray(packed_sources, dtype=np.int64)
        stack_capacity = 8 * self.max_depth + 16
        out = np.zeros((n, 3), dtype=np.float64)
        for target_start in range(0, n, self.target_batch_size):
            target_end = min(n, target_start + self.target_batch_size)
            out[target_start:target_end] = _parcourir_octree_compile_avec_feuilles(
                positions,
                masses,
                active_mask,
                centres,
                half,
                node_masses,
                com,
                children,
                leaf_offsets,
                leaf_counts,
                leaf_sources,
                root,
                self.theta,
                self.softening_m * self.softening_m,
                stack_capacity,
                self.target_block_size,
                target_start,
                target_end,
            )
        return out
