import numpy as np

from universe_sim.constants import C
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.simulation.large_scale_engine import DomainePopulationSR
from universe_sim.simulation.large_scale_multirate import SimulationGrandeEchelleMultiTaux
from universe_sim.simulation.multirate import CadenceEvolution
from universe_sim.values import Instant


def sr_backend(name, beta):
    mass = 1000.
    gamma = 1 / np.sqrt(1 - beta * beta)
    momentum = np.array([[gamma * mass * beta * C, 0., 0.]])
    velocity = np.array([[beta * C, 0., 0.]])
    return ArrayStateBackend(
        (name,), np.zeros((1, 3)), velocity, momentum, np.array([mass]),
        np.zeros(1), np.zeros(1), np.ones(1, dtype=bool), np.ones(1, dtype=np.int8),
    )


def test_distinct_cadences_reach_same_final_coordinate_time():
    fast = DomainePopulationSR("fast", sr_backend("a", .8))
    slow = DomainePopulationSR("slow", sr_backend("b", .5))
    simulation = SimulationGrandeEchelleMultiTaux(
        Instant(100), [fast, slow],
        {"fast": CadenceEvolution("fast", 2), "slow": CadenceEvolution("slow", 5)},
    )
    simulation.executer(10)
    assert simulation.simultanes()
    assert simulation.instant_barriere.seconds == 110
    assert simulation.temps_domaine("fast").seconds == 110
    assert simulation.temps_domaine("slow").seconds == 110
    assert np.allclose(fast.backend.proper_times_s, [6.])
    assert np.allclose(slow.backend.proper_times_s, [10 * np.sqrt(1 - .5 ** 2)])


def test_partial_final_steps_synchronize_non_commensurate_cadences():
    a = DomainePopulationSR("a", sr_backend("a", .1))
    b = DomainePopulationSR("b", sr_backend("b", .2))
    simulation = SimulationGrandeEchelleMultiTaux(
        Instant(0), [a, b], {"a": CadenceEvolution("a", 7), "b": CadenceEvolution("b", 11)}
    )
    simulation.executer(25)
    assert simulation.instant_barriere.seconds == 25


def test_coupling_policy_sees_unsynchronized_domain_times_explicitly():
    seen = []
    a = DomainePopulationSR("a", sr_backend("a", .1))
    b = DomainePopulationSR("b", sr_backend("b", .2))

    def policy(simulation, deadline):
        seen.append((deadline.offset_s, simulation.temps_domaine("a").seconds, simulation.temps_domaine("b").seconds))

    simulation = SimulationGrandeEchelleMultiTaux(
        Instant(0), [a, b],
        {"a": CadenceEvolution("a", 2), "b": CadenceEvolution("b", 5)}, policy,
    )
    simulation.executer(6)
    assert any(abs(ta - tb) > 0 for _, ta, tb in seen[1:])
    assert simulation.instant_barriere.seconds == 6


def test_second_segment_starts_from_barrier_and_accumulates_time():
    a = DomainePopulationSR("a", sr_backend("a", .1))
    b = DomainePopulationSR("b", sr_backend("b", .2))
    simulation = SimulationGrandeEchelleMultiTaux(
        Instant(3), [a, b], {"a": CadenceEvolution("a", 4), "b": CadenceEvolution("b", 9)}
    )
    simulation.executer(10)
    assert simulation.instant_barriere.seconds == 13
    simulation.executer(5)
    assert simulation.instant_barriere.seconds == 18
