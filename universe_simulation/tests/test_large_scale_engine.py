import numpy as np

from universe_sim.constants import C
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.simulation.large_scale_engine import (
    DomainePopulationClassique,
    DomainePopulationSR,
    SimulationGrandeEchelleMultiRegime,
)
from universe_sim.values import Instant


def classical_backend():
    return ArrayStateBackend(
        ("star", "tracer"),
        np.array([[0., 0., 0.], [1e7, 0., 0.]]),
        np.array([[0., 0., 0.], [0., 1., 0.]]),
        np.zeros((2, 3)),
        np.array([1e20, 0.]),
        np.zeros(2),
        np.full(2, np.nan),
        np.ones(2, dtype=bool),
        np.zeros(2, dtype=np.int8),
    )


def sr_backend(n=3, beta=.8):
    masses = np.arange(1, n + 1, dtype=float) * 1000
    gamma = 1 / np.sqrt(1 - beta * beta)
    momentum = np.zeros((n, 3))
    momentum[:, 0] = gamma * masses * beta * C
    velocity = np.zeros((n, 3))
    velocity[:, 0] = beta * C
    return ArrayStateBackend(
        tuple(f"ship-{i}" for i in range(n)), np.zeros((n, 3)), velocity, momentum,
        masses, np.zeros(n), np.zeros(n), np.ones(n, dtype=bool), np.ones(n, dtype=np.int8)
    )


def test_hot_domains_advance_without_object_synchronization():
    classical = classical_backend()
    sr = sr_backend()
    simulation = SimulationGrandeEchelleMultiRegime(
        Instant(100.),
        [DomainePopulationClassique("classical", classical), DomainePopulationSR("sr", sr)],
    )
    simulation.avancer(10.)
    assert simulation.instant_courant.seconds == 110.
    assert simulation.pas_effectues == 1
    assert classical.positions_m[1, 1] > 0
    assert np.allclose(sr.positions_m[:, 0], .8 * C * 10, rtol=1e-13)
    assert np.allclose(sr.proper_times_s, 6., rtol=1e-13)


def test_overlapping_domain_ownership_is_rejected():
    classical = classical_backend()
    sr = sr_backend(n=1)
    sr.body_ids = ("star",)
    sr._index = {"star": 0}
    try:
        SimulationGrandeEchelleMultiRegime(
            Instant(0),
            [DomainePopulationClassique("c", classical), DomainePopulationSR("s", sr)],
        )
    except ValueError as exc:
        assert "already owned" in str(exc)
    else:
        raise AssertionError("expected overlap rejection")


def test_sr_hot_force_provider_uses_dpdt_not_newtonian_dvdt():
    sr = sr_backend(n=1, beta=0.)

    def force(backend, instant):
        result = np.zeros_like(backend.momenta_kg_m_s)
        result[:, 0] = 1e12
        return result

    simulation = SimulationGrandeEchelleMultiRegime(
        Instant(0), [DomainePopulationSR("sr", sr, force_provider=force)]
    )
    simulation.executer(1000, 100)
    assert sr.momenta_kg_m_s[0, 0] == 1e15
    assert np.linalg.norm(sr.velocities_m_s[0]) < C
    assert 0 < sr.proper_times_s[0] <= 1000


def test_execute_uses_partial_final_step_without_overshoot():
    sr = sr_backend(n=1, beta=.1)
    simulation = SimulationGrandeEchelleMultiRegime(Instant(5), [DomainePopulationSR("sr", sr)])
    simulation.executer(25, 7)
    assert abs(simulation.instant_courant.seconds - 30) < 1e-12
    assert simulation.pas_effectues == 4
