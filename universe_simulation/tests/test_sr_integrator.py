import unittest

from universe_sim.constants import C
from universe_sim.relativistic_values import impulsion_relativiste
from universe_sim.simulation import EtatParticuleSR, IntegrateurRelativisteSpecial
from universe_sim.values import Vecteur3


class SpecialRelativityIntegratorTests(unittest.TestCase):
    def test_zero_force_keeps_velocity_and_advances_proper_time(self):
        mass = 500.0
        velocity = Vecteur3(0.6 * C, 0.0, 0.0)
        state = EtatParticuleSR(Vecteur3.zero(), impulsion_relativiste(mass, velocity), mass)
        integrator = IntegrateurRelativisteSpecial()
        integrator.avancer_force_constante(state, Vecteur3.zero(), 10.0)
        self.assertLess(abs(state.vitesse_m_s.x - velocity.x) / C, 1e-14)
        self.assertAlmostEqual(state.temps_propre_s, 8.0, places=12)

    def test_large_continuous_force_never_crosses_light_speed(self):
        state = EtatParticuleSR(Vecteur3.zero(), Vecteur3.zero(), 1000.0)
        integrator = IntegrateurRelativisteSpecial()
        force = Vecteur3(1.0e12, 0.0, 0.0)
        for _ in range(2000):
            integrator.avancer_force_constante(state, force, 1000.0)
        self.assertLess(state.vitesse_m_s.norm(), C)
        self.assertGreater(state.gamma, 1.0)
        self.assertGreater(state.temps_propre_s, 0.0)
        self.assertLess(state.temps_propre_s, 2_000_000.0)

    def test_force_changes_momentum_by_impulse(self):
        state = EtatParticuleSR(Vecteur3.zero(), Vecteur3.zero(), 200.0)
        integrator = IntegrateurRelativisteSpecial()
        force = Vecteur3(3000.0, -500.0, 100.0)
        dt = 7.5
        integrator.avancer_force_constante(state, force, dt)
        expected = force * dt
        self.assertLess((state.impulsion_kg_m_s - expected).norm(), 1e-12)


if __name__ == "__main__":
    unittest.main()
