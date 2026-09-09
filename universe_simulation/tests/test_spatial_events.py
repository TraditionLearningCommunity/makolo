import numpy as np

from universe_sim.simulation.spatial_events import IndexSpatialGrille, detecter_franchissements_sphere
from universe_sim.values import Vecteur3


def test_long_step_can_enter_and_leave_same_sphere():
    crossings = detecter_franchissements_sphere(Vecteur3(-10, 0, 0), Vecteur3(10, 0, 0), 2)
    assert len(crossings) == 2
    assert crossings[0].entree and not crossings[1].entree
    assert abs(crossings[0].fraction_pas - .4) < 1e-12
    assert abs(crossings[1].fraction_pas - .6) < 1e-12


def test_tangent_is_not_entry_or_exit():
    assert detecter_franchissements_sphere(Vecteur3(-10, 2, 0), Vecteur3(10, 2, 0), 2) == ()


def test_uniform_grid_matches_bruteforce_radius_query():
    rng = np.random.default_rng(4)
    positions = rng.uniform(-100, 100, size=(200, 3))
    radius = 18.
    got = set(IndexSpatialGrille(10).paires_dans_distance(positions, radius))
    expected = set()
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            if np.linalg.norm(positions[j] - positions[i]) <= radius:
                expected.add((i, j))
    assert got == expected


def test_inactive_rows_are_excluded_from_spatial_pairs():
    positions = np.array([[0., 0, 0], [1, 0, 0], [2, 0, 0]])
    active = np.array([True, False, True])
    got = IndexSpatialGrille(1).paires_dans_distance(positions, 3, active)
    assert got == ((0, 2),)
