import numpy as np

from universe_sim.constants import C
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.simulation.sr_population import IntegrateurPopulationSRTableau


def sr_backend(n=4, beta=.8):
    masses = np.linspace(2, 5, n)
    gamma = 1 / np.sqrt(1 - beta * beta)
    momentum = np.zeros((n, 3))
    momentum[:, 0] = gamma * masses * beta * C
    velocity = np.zeros((n, 3))
    velocity[:, 0] = beta * C
    return ArrayStateBackend(
        tuple(str(i) for i in range(n)), np.zeros((n, 3)), velocity, momentum,
        masses, np.zeros(n), np.zeros(n), np.ones(n, dtype=bool), np.ones(n, dtype=np.int8)
    )


def test_zero_force_is_inertial_and_accumulates_proper_time():
    backend = sr_backend(beta=.8)
    IntegrateurPopulationSRTableau().avancer_forces_constantes(backend, np.zeros((4, 3)), 10)
    assert np.allclose(backend.positions_m[:, 0], .8 * C * 10, rtol=1e-14)
    assert np.allclose(backend.proper_times_s, 6., rtol=1e-14)


def test_arbitrarily_large_impulse_remains_subluminal():
    backend = sr_backend(n=2, beta=0.)
    force = np.zeros((2, 3))
    force[:, 0] = 1e30
    IntegrateurPopulationSRTableau().avancer_forces_constantes(backend, force, 1e9)
    speeds = np.linalg.norm(backend.velocities_m_s, axis=1)
    assert np.all(speeds < C)
    assert np.all(np.isfinite(speeds))


def test_inactive_sr_row_does_not_advance():
    backend = sr_backend(n=2, beta=.5)
    backend.active[1] = False
    before = backend.copier()
    IntegrateurPopulationSRTableau().avancer_forces_constantes(backend, np.zeros((2, 3)), 20)
    assert backend.positions_m[0, 0] > 0
    assert np.allclose(backend.positions_m[1], before.positions_m[1])
    assert backend.proper_times_s[1] == before.proper_times_s[1]


def test_thousands_of_sr_vehicles_remain_causal_under_distinct_forces():
    rng = np.random.default_rng(20260909)
    n = 5000
    masses = 10 ** rng.uniform(2, 8, size=n)
    directions = rng.normal(size=(n, 3))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    beta = rng.uniform(0.0, 0.999999, size=n)
    gamma = 1.0 / np.sqrt(1.0 - beta * beta)
    momenta = directions * (gamma * masses * beta * C)[:, None]
    velocities = directions * (beta * C)[:, None]
    backend = ArrayStateBackend(
        tuple(f"ship-{i}" for i in range(n)), np.zeros((n, 3)), velocities, momenta,
        masses, np.zeros(n), np.zeros(n), np.ones(n, dtype=bool), np.ones(n, dtype=np.int8)
    )
    forces = rng.normal(size=(n, 3)) * 1e12
    IntegrateurPopulationSRTableau().avancer_forces_constantes(backend, forces, 3600.0)
    speeds = np.linalg.norm(backend.velocities_m_s, axis=1)
    assert np.all(np.isfinite(backend.positions_m))
    assert np.all(np.isfinite(backend.momenta_kg_m_s))
    assert np.all(speeds < C)
    assert np.all(backend.proper_times_s >= 0.0)
    assert np.all(backend.proper_times_s <= 3600.0)
