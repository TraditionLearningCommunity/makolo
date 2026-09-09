from types import SimpleNamespace

import numpy as np

from universe_sim.regimes import NiveauActiviteCalcul
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.values import Vecteur3
from universe_sim.visuals.lod import RequeteVisuelleLOD, SelecteurVisuelLOD


def _backend(n=1000):
    rng = np.random.default_rng(5)
    return ArrayStateBackend(
        tuple(f"b{i}" for i in range(n)),
        rng.uniform(-100, 100, size=(n, 3)),
        np.zeros((n, 3)),
        np.zeros((n, 3)),
        np.arange(1, n + 1, dtype=float),
        np.zeros(n),
        np.full(n, np.nan),
        np.ones(n, dtype=bool),
        np.zeros(n, dtype=np.int8),
    )


def test_selection_respects_budget_and_priority_and_is_deterministic():
    backend = _backend()
    query = RequeteVisuelleLOD(budget_objets=50, ids_prioritaires=("b0", "b10"), seed=42)
    first = SelecteurVisuelLOD().selectionner(backend, query)
    second = SelecteurVisuelLOD().selectionner(backend, query)
    assert len(first.body_ids) == 50
    assert "b0" in first.body_ids and "b10" in first.body_ids
    assert first.body_ids == second.body_ids


def test_radius_filters_objects():
    backend = _backend(200)
    query = RequeteVisuelleLOD(centre_m=Vecteur3(), rayon_m=10, budget_objets=200)
    selection = SelecteurVisuelLOD().selectionner(backend, query)
    assert np.all(np.linalg.norm(selection.positions_m, axis=1) <= 10 + 1e-12)


def test_aggregated_system_hides_its_materialized_members():
    backend = _backend(100)
    state = SimpleNamespace(
        niveau_activite=NiveauActiviteCalcul.AGGREGATED,
        barycentre_m=Vecteur3(),
        rayon_couverture_m=50.,
        masse_kg=1e20,
        corps_ids=tuple(f"b{i}" for i in range(20)),
    )
    registry = SimpleNamespace(etats_agreges={"sys": state}, parent_par_systeme={"sys": None})
    selection = SelecteurVisuelLOD().selectionner(backend, RequeteVisuelleLOD(budget_objets=100), registry)
    assert len(selection.agregats) == 1
    assert all(f"b{i}" not in selection.body_ids for i in range(20))
