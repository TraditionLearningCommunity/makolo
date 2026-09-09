import numpy as np
import pytest
from universe_sim.gravity import (
    NUMBA_DISPONIBLE,
    SolveurGraviteBarnesHut,
    SolveurGraviteBarnesHutCompile,
)

pytestmark = pytest.mark.skipif(not NUMBA_DISPONIBLE, reason="Numba performance extra is not installed")


def test_compiled_traversal_matches_reference_barnes_hut():
    rng = np.random.default_rng(81)
    positions = rng.uniform(-2e12, 2e12, size=(300, 3))
    masses = 10 ** rng.uniform(18, 25, size=300)
    ref = SolveurGraviteBarnesHut(theta=.45, leaf_capacity=8).accelerations(positions, masses)
    fast = SolveurGraviteBarnesHutCompile(theta=.45, leaf_capacity=8).accelerations(positions, masses)
    assert np.allclose(fast, ref, rtol=5e-13, atol=1e-18)


def test_compiled_solver_preserves_zero_mass_tracer_and_inactive_semantics():
    positions = np.array([[0., 0., 0.], [1e8, 0, 0.], [2e8, 0, 0.], [3e8, 0, 0.]])
    masses = np.array([1e25, 2e25, 0., 4e25])
    active = np.array([True, True, True, False])
    ref = SolveurGraviteBarnesHut(theta=.4, leaf_capacity=1).accelerations(positions, masses, active)
    fast = SolveurGraviteBarnesHutCompile(theta=.4, leaf_capacity=1).accelerations(positions, masses, active)
    assert np.allclose(fast, ref, rtol=1e-14, atol=0)
    assert np.allclose(fast[3], 0)
