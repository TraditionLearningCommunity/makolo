import numpy as np
from universe_sim.gravity import SolveurGraviteBarnesHut, SolveurGraviteDirect


def _relative_vector_error(approx, exact):
    num=np.linalg.norm(approx-exact,axis=1)
    den=np.maximum(np.linalg.norm(exact,axis=1),1e-300)
    return num/den


def test_tiny_theta_converges_to_direct_solution():
    rng=np.random.default_rng(12)
    positions=rng.normal(size=(96,3))*2e10
    masses=10**rng.uniform(18,24,size=96)
    direct=SolveurGraviteDirect(block_size=32).accelerations(positions,masses)
    bh=SolveurGraviteBarnesHut(theta=1e-6,leaf_capacity=4).accelerations(positions,masses)
    assert np.allclose(bh,direct,rtol=2e-12,atol=1e-18)


def test_practical_theta_has_bounded_error_against_direct():
    rng=np.random.default_rng(33)
    positions=rng.uniform(-1e12,1e12,size=(256,3))
    masses=10**rng.uniform(18,25,size=256)
    direct=SolveurGraviteDirect(block_size=64).accelerations(positions,masses)
    bh=SolveurGraviteBarnesHut(theta=.45,leaf_capacity=8).accelerations(positions,masses)
    err=_relative_vector_error(bh,direct)
    assert np.median(err) < 3e-3
    assert np.quantile(err,.95) < 2e-2


def test_target_inside_node_is_not_self_aggregated():
    positions=np.array([[0.,0.,0.],[1e7,0,0.],[2e7,0,0.],[4e7,0,0.]])
    masses1=np.array([5e20,2e20,3e20,4e20])
    masses2=masses1.copy(); masses2[0]=5e30
    solver=SolveurGraviteBarnesHut(theta=10.,leaf_capacity=1)
    a1=solver.accelerations(positions,masses1)
    a2=solver.accelerations(positions,masses2)
    assert np.all(np.isfinite(a1))
    # A body's own mass must not alter its own acceleration. If an ancestor
    # containing the target were accepted as an aggregate, this would fail.
    assert np.allclose(a1[0],a2[0],rtol=1e-14,atol=0)


def test_zero_mass_tracer_works_with_tree():
    positions=np.array([[0.,0.,0.],[1e8,0,0.],[2e8,0,0.]])
    masses=np.array([1e25,2e25,0.])
    direct=SolveurGraviteDirect().accelerations(positions,masses)
    bh=SolveurGraviteBarnesHut(theta=.5,leaf_capacity=1).accelerations(positions,masses)
    assert np.allclose(bh[2],direct[2],rtol=1e-14)
