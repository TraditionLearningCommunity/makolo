import numpy as np
import pytest
from universe_sim.constants import G
from universe_sim.gravity import SolveurGraviteDirect


def test_two_body_matches_newton():
    positions=np.array([[0.,0.,0.],[10.,0.,0.]])
    masses=np.array([2.,3.])
    a=SolveurGraviteDirect(block_size=1).accelerations(positions,masses)
    assert np.allclose(a[0],[G*3/100,0,0],rtol=1e-14)
    assert np.allclose(a[1],[-G*2/100,0,0],rtol=1e-14)


def test_zero_mass_tracer_feels_gravity_but_does_not_source_it():
    positions=np.array([[0.,0.,0.],[4.,0.,0.]])
    masses=np.array([10.,0.])
    a=SolveurGraviteDirect().accelerations(positions,masses)
    assert np.allclose(a[0],0)
    assert np.allclose(a[1],[-G*10/16,0,0])


def test_blocking_does_not_change_result():
    rng=np.random.default_rng(4)
    positions=rng.normal(size=(37,3))*1e6
    masses=rng.uniform(1,10,size=37)
    a1=SolveurGraviteDirect(block_size=3).accelerations(positions,masses)
    a2=SolveurGraviteDirect(block_size=100).accelerations(positions,masses)
    assert np.allclose(a1,a2,rtol=2e-15,atol=0)


def test_distinct_coincident_massive_centers_are_rejected_without_softening():
    positions=np.zeros((2,3)); masses=np.array([1.,2.])
    with pytest.raises(ValueError,match='coincide'):
        SolveurGraviteDirect().accelerations(positions,masses)


def test_inactive_rows_neither_source_nor_advance():
    positions=np.array([[0.,0.,0.],[10.,0.,0.],[20.,0.,0.]])
    masses=np.array([2.,3.,4.]); active=np.array([True,False,True])
    a=SolveurGraviteDirect().accelerations(positions,masses,active)
    assert np.allclose(a[1],0)
    assert np.allclose(a[0],[G*4/400,0,0])
