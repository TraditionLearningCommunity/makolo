import math
import unittest

from universe_sim.constants import C, DAY
from universe_sim.simulation import EtatParticuleSR, IntegrateurRelativisteSpecial
from universe_sim.values import Vecteur3


class ProperAccelerationTests(unittest.TestCase):
    def test_one_g_for_one_coordinate_year_remains_subluminal(self):
        state = EtatParticuleSR(Vecteur3.zero(), Vecteur3.zero(), 1000.0)
        integrator = IntegrateurRelativisteSpecial()
        dt = 365.25 * DAY
        integrator.avancer_acceleration_propre_colineaire(state, 9.80665, Vecteur3(1.0, 0.0, 0.0), dt)
        expected = C * math.tanh(math.asinh(9.80665 * dt / C))
        self.assertLess(state.vitesse_m_s.norm(), C)
        self.assertLess(abs(state.vitesse_m_s.x - expected) / C, 1e-13)
        self.assertLess(state.temps_propre_s, dt)

    def test_accelerate_then_decelerate_returns_near_rest(self):
        state = EtatParticuleSR(Vecteur3.zero(), Vecteur3.zero(), 1000.0)
        integrator = IntegrateurRelativisteSpecial()
        axis = Vecteur3(1.0, 0.0, 0.0)
        dt = 100.0 * DAY
        integrator.avancer_acceleration_propre_colineaire(state, 9.80665, axis, dt)
        peak = state.vitesse_m_s.norm()
        integrator.avancer_acceleration_propre_colineaire(state, -9.80665, axis, dt)
        self.assertLess(state.vitesse_m_s.norm(), peak)
        self.assertLess(state.vitesse_m_s.norm() / C, 1e-12)

    def test_non_collinear_initial_velocity_is_rejected_by_exact_solver(self):
        mass = 1000.0
        state = EtatParticuleSR(Vecteur3.zero(), Vecteur3(0.0, mass * 1000.0, 0.0), mass)
        integrator = IntegrateurRelativisteSpecial()
        with self.assertRaises(ValueError):
            integrator.avancer_acceleration_propre_colineaire(state, 1.0, Vecteur3(1.0, 0.0, 0.0), 10.0)


if __name__ == "__main__":
    unittest.main()
