import numpy as np

from universe_sim.gravity import SolveurGraviteDirect
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.simulation.population import IntegrateurPopulationNewtonienneTableau


def _backend(positions, velocities, masses, active=None):
    n = len(masses)
    return ArrayStateBackend(
        tuple(str(i) for i in range(n)),
        np.asarray(positions, dtype=float),
        np.asarray(velocities, dtype=float),
        np.asarray(velocities, dtype=float) * np.asarray(masses, dtype=float)[:, None],
        np.asarray(masses, dtype=float),
        np.zeros(n),
        np.full(n, np.nan),
        np.ones(n, dtype=bool) if active is None else np.asarray(active, dtype=bool),
        np.zeros(n, dtype=np.int8),
    )


def test_velocity_verlet_preserves_center_of_mass_for_two_body_pair():
    backend = _backend([[-5., 0, 0], [5., 0, 0]], [[0, -.1, 0], [0, .1, 0]], [2e12, 2e12])
    integrator = IntegrateurPopulationNewtonienneTableau(SolveurGraviteDirect())
    com0 = np.average(backend.positions_m, axis=0, weights=backend.masses_kg)
    p0 = (backend.velocities_m_s * backend.masses_kg[:, None]).sum(axis=0)
    for _ in range(100):
        integrator.avancer(backend, .01)
    com1 = np.average(backend.positions_m, axis=0, weights=backend.masses_kg)
    p1 = (backend.velocities_m_s * backend.masses_kg[:, None]).sum(axis=0)
    assert np.allclose(com1, com0, atol=1e-10)
    assert np.allclose(p1, p0, atol=1e-8)


def test_zero_mass_tracer_moves_and_inactive_row_does_not():
    backend = _backend(
        [[0., 0, 0], [10., 0, 0], [20., 0, 0]],
        [[0, 0, 0], [1, 0, 0], [3, 0, 0]],
        [1e12, 0, 1e12],
        [True, True, False],
    )
    before = backend.positions_m.copy()
    IntegrateurPopulationNewtonienneTableau().avancer(backend, .5)
    assert backend.positions_m[1, 0] > before[1, 0]
    assert np.allclose(backend.positions_m[2], before[2])


def test_sr_rows_are_rejected():
    backend = _backend([[0., 0, 0]], [[0, 0, 0]], [1.])
    backend.regime_codes[0] = 1
    try:
        IntegrateurPopulationNewtonienneTableau().avancer(backend, 1.)
    except ValueError as exc:
        assert "only classical" in str(exc)
    else:
        raise AssertionError("expected SR row rejection")
