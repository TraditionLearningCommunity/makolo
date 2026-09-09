"""Spatial broad phase and continuous spherical-boundary event detection."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import floor, sqrt

import numpy as np

from ..events import EvenementPhysique, TypeEvenement
from ..values import Instant, Vecteur3


@dataclass(frozen=True, slots=True)
class FranchissementSphere:
    fraction_pas: float
    entree: bool


@dataclass(frozen=True, slots=True)
class ZoneSpheriquePhysique:
    centre_id: str
    rayon_m: float
    type_entree: TypeEvenement
    type_sortie: TypeEvenement
    nom: str = "zone"

    def __post_init__(self) -> None:
        if self.rayon_m <= 0:
            raise ValueError("Spherical zone radius must be positive")


def detecter_franchissements_sphere(relative_avant: Vecteur3, relative_apres: Vecteur3, rayon_m: float) -> tuple[FranchissementSphere, ...]:
    """Find every genuine crossing of a sphere during a linearly interpolated step.

    Two roots are retained when a long numerical step enters and leaves the
    sphere before its end. Pure tangencies do not change inside/outside state
    and therefore are not emitted as entry/exit events.
    """
    radius = float(rayon_m)
    if radius <= 0:
        raise ValueError("Sphere radius must be positive")
    r0 = np.asarray(relative_avant.as_tuple(), dtype=np.float64)
    r1 = np.asarray(relative_apres.as_tuple(), dtype=np.float64)
    dr = r1 - r0
    a = float(np.dot(dr, dr))
    b = 2.0 * float(np.dot(r0, dr))
    c = float(np.dot(r0, r0) - radius * radius)
    scale = max(1.0, radius * radius, float(np.dot(r0, r0)), float(np.dot(r1, r1)))
    tol = np.finfo(np.float64).eps * scale * 64.0
    if a <= tol:
        return ()
    discriminant = b * b - 4.0 * a * c
    if discriminant <= tol:
        return ()
    root = sqrt(max(0.0, discriminant))
    roots = sorted(((-b - root) / (2.0 * a), (-b + root) / (2.0 * a)))
    result = []
    fraction_tol = 1e-12
    for s in roots:
        if s <= fraction_tol or s > 1.0 + fraction_tol:
            continue
        s = min(1.0, max(0.0, s))
        r = r0 + s * dr
        derivative = 2.0 * float(np.dot(r, dr))
        if abs(derivative) <= tol:
            continue
        result.append(FranchissementSphere(s, derivative < 0.0))
    return tuple(result)


def evenements_zone_spherique(
    mobile_id: str,
    zone: ZoneSpheriquePhysique,
    position_mobile_avant: Vecteur3,
    position_mobile_apres: Vecteur3,
    centre_avant: Vecteur3,
    centre_apres: Vecteur3,
    instant_avant: Instant,
    dt_s: float,
) -> list[EvenementPhysique]:
    if dt_s <= 0:
        raise ValueError("Time step must be positive")
    rel0 = position_mobile_avant - centre_avant
    rel1 = position_mobile_apres - centre_apres
    crossings = detecter_franchissements_sphere(rel0, rel1, zone.rayon_m)
    events = []
    displacement = position_mobile_apres - position_mobile_avant
    for crossing in crossings:
        fraction = crossing.fraction_pas
        position = position_mobile_avant + displacement * fraction
        events.append(
            EvenementPhysique(
                zone.type_entree if crossing.entree else zone.type_sortie,
                Instant(instant_avant.seconds + dt_s * fraction),
                (mobile_id, zone.centre_id),
                position,
                {
                    "zone": zone.nom,
                    "rayon_m": zone.rayon_m,
                    "fraction_pas": fraction,
                    "localisation": "intersection_quadratique_continue",
                },
            )
        )
    return events


@dataclass(frozen=True, slots=True)
class IndexSpatialGrille:
    """Uniform-grid broad phase for local Euclidean neighborhoods.

    This is a local-space optimization, not a replacement for the astronomical
    hierarchy or Barnes-Hut. It is intended for collision/encounter candidate
    generation inside a materialized region.
    """

    taille_cellule_m: float

    def __post_init__(self) -> None:
        if self.taille_cellule_m <= 0:
            raise ValueError("Spatial cell size must be positive")

    def _cell(self, position: np.ndarray) -> tuple[int, int, int]:
        h = self.taille_cellule_m
        return (floor(position[0] / h), floor(position[1] / h), floor(position[2] / h))

    def paires_dans_distance(self, positions_m: np.ndarray, distance_m: float, active: np.ndarray | None = None) -> tuple[tuple[int, int], ...]:
        positions = np.asarray(positions_m, dtype=np.float64)
        if positions.ndim != 2 or positions.shape[1] != 3:
            raise ValueError("positions_m must have shape (N,3)")
        n = positions.shape[0]
        if distance_m < 0:
            raise ValueError("Search distance must be non-negative")
        mask = np.ones(n, dtype=np.bool_) if active is None else np.asarray(active, dtype=np.bool_)
        if mask.shape != (n,):
            raise ValueError("active must have shape (N,)")
        reach = max(0, int(np.ceil(distance_m / self.taille_cellule_m)))
        cells: dict[tuple[int, int, int], list[int]] = {}
        for i in np.flatnonzero(mask):
            cells.setdefault(self._cell(positions[i]), []).append(int(i))
        threshold2 = float(distance_m) ** 2
        pairs: set[tuple[int, int]] = set()
        offsets = tuple(product(range(-reach, reach + 1), repeat=3))
        for cell, indices in cells.items():
            for offset in offsets:
                neighbor = (cell[0] + offset[0], cell[1] + offset[1], cell[2] + offset[2])
                others = cells.get(neighbor)
                if others is None:
                    continue
                for i in indices:
                    for j in others:
                        if j <= i:
                            continue
                        delta = positions[j] - positions[i]
                        if float(np.dot(delta, delta)) <= threshold2:
                            pairs.add((i, j))
        return tuple(sorted(pairs))
