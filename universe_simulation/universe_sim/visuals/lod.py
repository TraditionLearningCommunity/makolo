"""Level-of-detail queries for rendering very large simulated populations."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..regimes import NiveauActiviteCalcul
from ..simulation.array_backend import ArrayStateBackend
from ..simulation.hierarchy import RegistreHierarchiqueUnivers
from ..values import Vecteur3


@dataclass(frozen=True, slots=True)
class RequeteVisuelleLOD:
    centre_m: Vecteur3 = field(default_factory=Vecteur3.zero)
    rayon_m: float | None = None
    budget_objets: int = 10_000
    ids_prioritaires: tuple[str, ...] = ()
    fraction_masses_dominantes: float = 0.25
    seed: int = 0

    def __post_init__(self) -> None:
        if self.rayon_m is not None and self.rayon_m <= 0:
            raise ValueError("Visual query radius must be positive")
        if self.budget_objets < 1:
            raise ValueError("Visual object budget must be positive")
        if not 0.0 <= self.fraction_masses_dominantes <= 1.0:
            raise ValueError("Dominant-mass fraction must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class AgregatVisuelLOD:
    systeme_id: str
    centre_m: Vecteur3
    rayon_m: float
    masse_kg: float
    niveau: NiveauActiviteCalcul


@dataclass(frozen=True, slots=True)
class SelectionVisuelleLOD:
    body_indices: np.ndarray
    body_ids: tuple[str, ...]
    positions_m: np.ndarray
    masses_kg: np.ndarray
    agregats: tuple[AgregatVisuelLOD, ...]


class SelecteurVisuelLOD:
    """Select a bounded deterministic view without changing physical state."""

    @staticmethod
    def _agregats_visibles(registre: RegistreHierarchiqueUnivers | None, requete: RequeteVisuelleLOD):
        if registre is None:
            return (), set()
        aggregate_levels = {NiveauActiviteCalcul.AGGREGATED, NiveauActiviteCalcul.VISUAL_ONLY}
        selected = []
        hidden_body_ids: set[str] = set()
        centre = np.asarray(requete.centre_m.as_tuple(), dtype=np.float64)
        for system_id, state in registre.etats_agreges.items():
            if state.niveau_activite not in aggregate_levels:
                continue
            parent = registre.parent_par_systeme.get(system_id)
            hidden_by_parent = False
            while parent is not None:
                parent_state = registre.etats_agreges.get(parent)
                if parent_state is not None and parent_state.niveau_activite in aggregate_levels:
                    hidden_by_parent = True
                    break
                parent = registre.parent_par_systeme.get(parent)
            if hidden_by_parent:
                continue
            position = np.asarray(state.barycentre_m.as_tuple(), dtype=np.float64)
            if requete.rayon_m is not None:
                if float(np.linalg.norm(position - centre)) > requete.rayon_m + state.rayon_couverture_m:
                    continue
            selected.append(
                AgregatVisuelLOD(
                    system_id,
                    state.barycentre_m,
                    state.rayon_couverture_m,
                    state.masse_kg,
                    state.niveau_activite,
                )
            )
            hidden_body_ids.update(state.corps_ids)
        return tuple(selected), hidden_body_ids

    def selectionner(
        self,
        backend: ArrayStateBackend,
        requete: RequeteVisuelleLOD,
        registre: RegistreHierarchiqueUnivers | None = None,
    ) -> SelectionVisuelleLOD:
        agregats, hidden_ids = self._agregats_visibles(registre, requete)
        n = len(backend.body_ids)
        candidate = backend.active.copy()
        if hidden_ids:
            hidden = np.fromiter((body_id in hidden_ids for body_id in backend.body_ids), dtype=np.bool_, count=n)
            candidate &= ~hidden
        centre = np.asarray(requete.centre_m.as_tuple(), dtype=np.float64)
        if requete.rayon_m is not None:
            delta = backend.positions_m - centre
            candidate &= np.einsum("ij,ij->i", delta, delta) <= requete.rayon_m * requete.rayon_m

        candidate_indices = np.flatnonzero(candidate)
        if candidate_indices.size <= requete.budget_objets:
            selected = candidate_indices
        else:
            priority = []
            candidate_set = set(int(i) for i in candidate_indices)
            for body_id in requete.ids_prioritaires:
                try:
                    index = backend.index(body_id)
                except KeyError:
                    continue
                if index in candidate_set and index not in priority:
                    priority.append(index)
            priority = priority[: requete.budget_objets]
            chosen = set(priority)
            remaining_budget = requete.budget_objets - len(priority)

            remaining = np.asarray([i for i in candidate_indices if int(i) not in chosen], dtype=np.int64)
            dominant_budget = min(
                remaining_budget,
                int(round(requete.budget_objets * requete.fraction_masses_dominantes)),
            )
            if dominant_budget > 0 and remaining.size:
                order = np.argsort(backend.masses_kg[remaining], kind="stable")[::-1]
                dominant = remaining[order[:dominant_budget]]
                chosen.update(int(i) for i in dominant)
            remaining_budget = requete.budget_objets - len(chosen)
            if remaining_budget > 0:
                pool = np.asarray([i for i in candidate_indices if int(i) not in chosen], dtype=np.int64)
                if pool.size <= remaining_budget:
                    chosen.update(int(i) for i in pool)
                elif pool.size:
                    rng = np.random.default_rng(requete.seed)
                    sample = rng.choice(pool, size=remaining_budget, replace=False)
                    chosen.update(int(i) for i in sample)
            selected = np.asarray(sorted(chosen), dtype=np.int64)

        return SelectionVisuelleLOD(
            selected,
            tuple(backend.body_ids[int(i)] for i in selected),
            backend.positions_m[selected].copy(),
            backend.masses_kg[selected].copy(),
            agregats,
        )
