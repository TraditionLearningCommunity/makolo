"""Three-dimensional Barnes-Hut gravity for large Newtonian populations."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from ..constants import G


@dataclass(slots=True)
class _NoeudOctree:
    centre_m: np.ndarray
    demi_taille_m: float
    masse_kg: float
    centre_masse_m: np.ndarray
    indices_sources: np.ndarray | None
    enfants: tuple[int, ...] = ()

    @property
    def feuille(self) -> bool:
        return not self.enfants


@dataclass(frozen=True, slots=True)
class SolveurGraviteBarnesHut:
    """Barnes-Hut monopole solver using a 3D octree.

    ``theta`` is the standard opening-angle parameter. Smaller values open more
    nodes and converge toward the direct Newtonian solution. Leaves are always
    evaluated source by source. A node spatially containing the target is never
    accepted as an aggregate, which prevents hidden self-interaction.
    """

    theta: float = 0.6
    leaf_capacity: int = 16
    max_depth: int = 64
    softening_m: float = 0.0
    nom: str = "Barnes-Hut 3D"

    def __post_init__(self) -> None:
        if self.theta <= 0:
            raise ValueError("theta must be positive")
        if self.leaf_capacity < 1:
            raise ValueError("leaf_capacity must be positive")
        if self.max_depth < 1:
            raise ValueError("max_depth must be positive")
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
        source_indices = np.flatnonzero(active_mask & (masses > 0))
        if source_indices.size == 0:
            return accelerations
        source_positions = positions[source_indices]
        if self.softening_m == 0.0 and source_indices.size > 1:
            if np.unique(source_positions, axis=0).shape[0] != source_indices.size:
                raise ValueError("Distinct massive centers coincide")

        nodes, root = self._construire_octree(positions, masses, source_indices)
        epsilon2 = self.softening_m * self.softening_m
        for target_index in np.flatnonzero(active_mask):
            accelerations[target_index] = self._acceleration_cible(
                target_index,
                positions[target_index],
                positions,
                masses,
                nodes,
                root,
                epsilon2,
            )
        return accelerations

    def _construire_octree(
        self,
        positions: np.ndarray,
        masses: np.ndarray,
        source_indices: np.ndarray,
    ) -> tuple[list[_NoeudOctree], int]:
        source_positions = positions[source_indices]
        minimum = source_positions.min(axis=0)
        maximum = source_positions.max(axis=0)
        centre = (minimum + maximum) * 0.5
        span = float(np.max(maximum - minimum))
        scale = max(1.0, float(np.max(np.abs(centre))))
        half = max(span * 0.5, np.finfo(np.float64).eps * scale * 8.0)
        # Inflate by a few ulps so boundary points remain inside the root.
        half = float(np.nextafter(half, np.inf))
        nodes: list[_NoeudOctree] = []

        def build(indices: np.ndarray, node_centre: np.ndarray, node_half: float, depth: int) -> int:
            local_masses = masses[indices]
            total_mass = float(local_masses.sum())
            com = np.sum(positions[indices] * local_masses[:, None], axis=0) / total_mass
            node_index = len(nodes)
            nodes.append(_NoeudOctree(node_centre.copy(), node_half, total_mass, com, None, ()))
            if indices.size <= self.leaf_capacity or depth >= self.max_depth:
                nodes[node_index].indices_sources = indices.copy()
                return node_index

            octants = (
                (positions[indices, 0] >= node_centre[0]).astype(np.int8)
                | ((positions[indices, 1] >= node_centre[1]).astype(np.int8) << 1)
                | ((positions[indices, 2] >= node_centre[2]).astype(np.int8) << 2)
            )
            child_half = node_half * 0.5
            child_ids: list[int] = []
            for octant in range(8):
                mask = octants == octant
                if not np.any(mask):
                    continue
                signs = np.array(
                    [1.0 if octant & 1 else -1.0, 1.0 if octant & 2 else -1.0, 1.0 if octant & 4 else -1.0]
                )
                child_centre = node_centre + signs * child_half
                child_ids.append(build(indices[mask], child_centre, child_half, depth + 1))
            nodes[node_index].enfants = tuple(child_ids)
            return node_index

        root = build(source_indices, centre, half, 0)
        return nodes, root

    def _acceleration_cible(
        self,
        target_index: int,
        target_position: np.ndarray,
        positions: np.ndarray,
        masses: np.ndarray,
        nodes: list[_NoeudOctree],
        root: int,
        epsilon2: float,
    ) -> np.ndarray:
        acceleration = np.zeros(3, dtype=np.float64)
        stack = [root]
        while stack:
            node = nodes[stack.pop()]
            if node.feuille:
                assert node.indices_sources is not None
                indices = node.indices_sources
                delta = positions[indices] - target_position
                r2 = np.einsum("ij,ij->i", delta, delta)
                self_mask = indices == target_index
                if self.softening_m == 0.0:
                    coincident = (r2 == 0.0) & ~self_mask
                    if np.any(coincident):
                        source = int(indices[np.flatnonzero(coincident)[0]])
                        raise ValueError(
                            f"Distinct massive centers coincide: target index {target_index}, source index {source}"
                        )
                denom2 = r2 + epsilon2
                denom2[self_mask] = np.inf
                inv_r3 = denom2 ** -1.5
                acceleration += G * np.sum(delta * (masses[indices] * inv_r3)[:, None], axis=0)
                continue

            delta_com = node.centre_masse_m - target_position
            distance = float(np.linalg.norm(delta_com))
            contains_target = bool(np.all(np.abs(target_position - node.centre_m) <= node.demi_taille_m))
            size = 2.0 * node.demi_taille_m
            if not contains_target and distance > 0.0 and size / distance < self.theta:
                denom2 = distance * distance + epsilon2
                acceleration += G * node.masse_kg * delta_com / (denom2 ** 1.5)
            else:
                stack.extend(node.enfants)
        return acceleration
