import math
import unittest

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import C
from universe_sim.events import TypeEvenement
from universe_sim.relativistic_state import EtatCinematiqueRelativiste
from universe_sim.relativistic_values import impulsion_relativiste
from universe_sim.simulation.relativistic_rocket import (
    EvolutionFuseeRelativisteIdeale,
    IntegrateurFuseeRelativisteIdeale,
    ParametresFuseeRelativisteIdeale,
)
from universe_sim.simulation.sr_integrator import EtatParticuleSR
from universe_sim.states import EtatMassique, EtatPhysique
from universe_sim.systems import Univers
from universe_sim.values import GrandeurPhysique, Instant, Vecteur3


class RelativisticRocketTests(unittest.TestCase):
    def test_exhaust_speed_at_or_above_c_is_rejected(self):
        with self.assertRaises(ValueError):
            ParametresFuseeRelativisteIdeale(C, 1.0, 100.0)

    def test_mass_loss_generates_sub_light_ackeret_velocity(self):
        parameters = ParametresFuseeRelativisteIdeale(0.5 * C, 1.0, 500.0)
        integrator = IntegrateurFuseeRelativisteIdeale(parameters, dtau_max_s=1.0)
        state = EtatParticuleSR(Vecteur3.zero(), Vecteur3.zero(), 1000.0)
        result = integrator.avancer_temps_coordonne(state, 2000.0, Vecteur3(1.0, 0.0, 0.0))
        self.assertAlmostEqual(state.masse_repos_kg, 500.0, places=7)
        self.assertAlmostEqual(result.masse_consommee_kg, 500.0, places=7)
        self.assertIsNotNone(result.temps_coordonne_epuisement_s)
        assert result.temps_coordonne_epuisement_s is not None
        self.assertLess(result.temps_coordonne_epuisement_s, 2000.0)
        expected_eta = 0.5 * math.log(2.0)
        expected_velocity = C * math.tanh(expected_eta)
        self.assertLess(abs(state.vitesse_m_s.x - expected_velocity) / C, 2e-7)
        self.assertLess(state.vitesse_m_s.norm(), C)
        self.assertLess(state.temps_propre_s, 2000.0)

    def test_reverse_thrust_reduces_rapidity(self):
        parameters = ParametresFuseeRelativisteIdeale(0.2 * C, 0.5, 800.0)
        integrator = IntegrateurFuseeRelativisteIdeale(parameters, dtau_max_s=2.0)
        state = EtatParticuleSR(
            Vecteur3.zero(),
            impulsion_relativiste(1000.0, Vecteur3(0.5 * C, 0.0, 0.0)),
            1000.0,
        )
        before = state.vitesse_m_s.x
        integrator.avancer_temps_coordonne(
            state,
            100.0,
            Vecteur3(1.0, 0.0, 0.0),
            signe_poussee=-1.0,
        )
        self.assertLess(state.vitesse_m_s.x, before)

    def test_body_mass_state_and_fuel_exhaustion_event_are_updated(self):
        parameters = ParametresFuseeRelativisteIdeale(0.1 * C, 10.0, 900.0)
        integrator = IntegrateurFuseeRelativisteIdeale(parameters, dtau_max_s=0.1)
        body = CorpsPhysique(
            "rocket",
            EtatPhysique(
                Instant(0.0),
                massique=EtatMassique(GrandeurPhysique(1000.0, "kg")),
                relativiste=EtatCinematiqueRelativiste(),
            ),
        )
        universe = Univers("u", corps_physiques=[body])
        evolution = EvolutionFuseeRelativisteIdeale(body.id, integrator)
        events = evolution.avancer(universe, Instant(0.0), 30.0)
        self.assertAlmostEqual(body.masse().value, 900.0, places=7)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, TypeEvenement.EPUISEMENT_PROPERGOL)
        self.assertLess(events[0].instant.seconds, 30.0)


if __name__ == "__main__":
    unittest.main()
