"""Computational hierarchy derived from physical systems without changing their identity."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from ..regimes import NiveauActiviteCalcul
from ..systems import SystemePhysique, Univers
from ..values import Vecteur3


@dataclass(frozen=True, slots=True)
class EtatAgregeSysteme:
    systeme_id: str
    masse_kg: float
    barycentre_m: Vecteur3
    vitesse_barycentrique_m_s: Vecteur3
    rayon_couverture_m: float
    quadrupole_kg_m2: tuple[tuple[float, float, float], ...]
    corps_ids: tuple[str, ...]
    niveau_activite: NiveauActiviteCalcul = NiveauActiviteCalcul.AGGREGATED


@dataclass(slots=True)
class RegistreHierarchiqueUnivers:
    """Index and aggregate state for the physical system hierarchy.

    Systems remain physical semantic objects. This registry is a replaceable
    simulation-side view used for far-field approximation and level of detail.
    """

    univers: Univers
    systemes_par_id: dict[str, SystemePhysique] = field(init=False, default_factory=dict)
    parent_par_systeme: dict[str, str | None] = field(init=False, default_factory=dict)
    etats_agreges: dict[str, EtatAgregeSysteme] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._indexer()
        self.recalculer()

    def _indexer(self) -> None:
        self.systemes_par_id.clear()
        self.parent_par_systeme.clear()
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(systeme: SystemePhysique, parent: str | None) -> None:
            if systeme.id in visiting:
                raise ValueError(f"Cycle in system hierarchy at {systeme.nom}")
            if systeme.id in visited:
                previous = self.parent_par_systeme[systeme.id]
                if previous != parent and parent is not None:
                    raise ValueError(f"System {systeme.nom} has multiple computational parents")
                return
            existing = self.systemes_par_id.get(systeme.id)
            if existing is not None and existing is not systeme:
                raise ValueError(f"Duplicate system id: {systeme.id}")
            self.systemes_par_id[systeme.id] = systeme
            self.parent_par_systeme[systeme.id] = parent
            visiting.add(systeme.id)
            for child in systeme.sous_systemes:
                visit(child, systeme.id)
            visiting.remove(systeme.id)
            visited.add(systeme.id)

        child_ids = {child.id for systeme in self.univers.systemes_physiques for child in systeme.sous_systemes}
        roots = [systeme for systeme in self.univers.systemes_physiques if systeme.id not in child_ids]
        for root in roots:
            visit(root, None)
        for systeme in self.univers.systemes_physiques:
            if systeme.id not in visited:
                visit(systeme, None)

    def _corps_descendants(self, systeme: SystemePhysique) -> tuple[object, ...]:
        by_id: dict[str, object] = {}
        stack = [systeme]
        seen_systems: set[str] = set()
        while stack:
            current = stack.pop()
            if current.id in seen_systems:
                continue
            seen_systems.add(current.id)
            for body in current.membres:
                by_id.setdefault(body.id, body)
            stack.extend(current.sous_systemes)
        return tuple(by_id.values())

    @staticmethod
    def _agregat(systeme: SystemePhysique, corps: Iterable[object], niveau: NiveauActiviteCalcul) -> EtatAgregeSysteme:
        bodies = tuple(corps)
        if not bodies:
            raise ValueError(f"System {systeme.nom} has no materialized bodies to aggregate")
        masses = []
        positions = []
        velocities = []
        radii = []
        ids = []
        frame_key = None
        for body in bodies:
            state = body.etat()
            if getattr(state, "espace_temps", None) is not None:
                raise ValueError(
                    f"{body.nom} uses curved-space-time coordinates; aggregate it only after an explicit common-chart projection"
                )
            position = state.position()
            velocity = state.vitesse()
            if position is None or velocity is None:
                raise ValueError(f"{body.nom} lacks translational kinematics for system aggregation")
            current_frame = (state.referentiel.id, state.systeme_coordonnees.nom)
            if frame_key is None:
                frame_key = current_frame
            elif current_frame != frame_key:
                raise ValueError("All bodies of a computational aggregate must share a reference frame and coordinate system")
            mass = body.masse().value
            if mass < 0:
                raise ValueError(f"{body.nom} has negative mass")
            masses.append(float(mass))
            positions.append(position.as_tuple())
            velocities.append(velocity.as_tuple())
            radii.append(0.0 if body.rayon_reference is None else max(0.0, float(body.rayon_reference.value)))
            ids.append(body.id)

        m = np.asarray(masses, dtype=np.float64)
        total = float(m.sum())
        if total <= 0:
            raise ValueError(f"System {systeme.nom} requires positive total mass for a barycentric aggregate")
        x = np.asarray(positions, dtype=np.float64)
        v = np.asarray(velocities, dtype=np.float64)
        bary = np.sum(x * m[:, None], axis=0) / total
        bary_v = np.sum(v * m[:, None], axis=0) / total
        rel = x - bary
        distances = np.linalg.norm(rel, axis=1) + np.asarray(radii, dtype=np.float64)
        coverage = float(distances.max(initial=0.0))

        quadrupole = np.zeros((3, 3), dtype=np.float64)
        identity = np.eye(3)
        for mass, r in zip(m, rel):
            r2 = float(np.dot(r, r))
            quadrupole += mass * (3.0 * np.outer(r, r) - r2 * identity)

        return EtatAgregeSysteme(
            systeme.id,
            total,
            Vecteur3.from_iterable(bary),
            Vecteur3.from_iterable(bary_v),
            coverage,
            tuple(tuple(float(value) for value in row) for row in quadrupole),
            tuple(ids),
            niveau,
        )

    def recalculer(self) -> None:
        previous_levels = {system_id: state.niveau_activite for system_id, state in self.etats_agreges.items()}
        self.etats_agreges = {}
        for system_id, systeme in self.systemes_par_id.items():
            bodies = self._corps_descendants(systeme)
            if not bodies:
                continue
            level = previous_levels.get(system_id, NiveauActiviteCalcul.AGGREGATED)
            self.etats_agreges[system_id] = self._agregat(systeme, bodies, level)

    def definir_niveau(self, systeme_id: str, niveau: NiveauActiviteCalcul) -> None:
        if systeme_id not in self.systemes_par_id:
            raise KeyError(systeme_id)
        state = self.etats_agreges.get(systeme_id)
        if state is None:
            raise ValueError("Cannot assign a computational level to an empty, non-materialized system")
        self.etats_agreges[systeme_id] = EtatAgregeSysteme(
            state.systeme_id,
            state.masse_kg,
            state.barycentre_m,
            state.vitesse_barycentrique_m_s,
            state.rayon_couverture_m,
            state.quadrupole_kg_m2,
            state.corps_ids,
            niveau,
        )

    def etat(self, systeme_id: str) -> EtatAgregeSysteme:
        return self.etats_agreges[systeme_id]
