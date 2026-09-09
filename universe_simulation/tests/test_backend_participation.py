import numpy as np

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import C
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.simulation.population import IntegrateurPopulationNewtonienneTableau
from universe_sim.simulation.sr_population import IntegrateurPopulationSRTableau
from universe_sim.states import EtatMassique, EtatPhysique
from universe_sim.relativistic_state import EtatCinematiqueRelativiste
from universe_sim.values import GrandeurPhysique, Instant, Vecteur3


def test_suspended_classical_row_remains_physically_active_but_is_not_evolved():
    backend = ArrayStateBackend(
        ("a", "b"),
        np.array([[0., 0., 0.], [10., 0., 0.]]),
        np.array([[1., 0., 0.], [2., 0., 0.]]),
        np.array([[1., 0., 0.], [2., 0., 0.]]),
        np.array([1., 1.]), np.zeros(2), np.full(2, np.nan),
        np.ones(2, dtype=bool), np.zeros(2, dtype=np.int8),
    )
    backend.suspendre_calcul("b")
    before = backend.positions_m.copy()
    # No gravity for this kinematic ownership test.
    class ZeroGravity:
        def accelerations(self, positions_m, masses_kg, active=None):
            return np.zeros_like(positions_m)
    IntegrateurPopulationNewtonienneTableau(ZeroGravity()).avancer(backend, 5.)
    assert backend.active[1]
    assert not backend.participating[1]
    assert backend.positions_m[0, 0] == before[0, 0] + 5.
    assert np.array_equal(backend.positions_m[1], before[1])


def test_suspended_sr_row_does_not_advance_or_accumulate_proper_time():
    beta = .8
    masses = np.array([1000., 1000.])
    gamma = 1 / np.sqrt(1 - beta * beta)
    momentum = np.array([[gamma * masses[0] * beta * C, 0., 0.], [gamma * masses[1] * beta * C, 0., 0.]])
    velocity = np.array([[beta * C, 0., 0.], [beta * C, 0., 0.]])
    backend = ArrayStateBackend(
        ("a", "b"), np.zeros((2, 3)), velocity, momentum, masses,
        np.zeros(2), np.zeros(2), np.ones(2, dtype=bool), np.ones(2, dtype=np.int8),
    )
    backend.suspendre_calcul("b")
    IntegrateurPopulationSRTableau().avancer_forces_constantes(backend, np.zeros((2, 3)), 10.)
    assert backend.positions_m[0, 0] > 0
    assert backend.positions_m[1, 0] == 0
    assert abs(backend.proper_times_s[0] - 6.) < 1e-12
    assert backend.proper_times_s[1] == 0
    assert backend.active[1]


def test_single_body_sync_does_not_require_full_registry_and_preserves_physical_activity():
    body = CorpsPhysique(
        "ship",
        EtatPhysique(
            Instant(0),
            massique=EtatMassique(GrandeurPhysique(1000., "kg")),
            relativiste=EtatCinematiqueRelativiste.depuis_vitesse(
                Vecteur3.zero(), Vecteur3(.5 * C, 0, 0), 1000.
            ),
        ),
        id="ship-id",
    )
    backend = ArrayStateBackend.depuis_corps([body])
    backend.positions_m[0, 0] = 1234.
    backend.suspendre_calcul(body.id)
    backend.synchroniser_un_corps(body)
    assert body.actif is True
    assert body.etat().relativiste.position.x == 1234.
    assert backend.participating[0] is np.False_ or not backend.participating[0]
    backend.reprendre_calcul(body.id)
    assert backend.participating[0]
