import unittest

from universe_sim.constants import C
from universe_sim.relativistic_values import quadrimpulsion_depuis_vitesse, quadrivitesse_depuis_vitesse
from universe_sim.services.relativistic_geometry import transformer_quadrimpulsion_lorentz
from universe_sim.values import Vecteur3


class FourVectorTransformTests(unittest.TestCase):
    def test_four_velocity_norm_is_minus_c_squared(self):
        u = quadrivitesse_depuis_vitesse(Vecteur3(0.7 * C, 0.2 * C, 0.0))
        self.assertLess(abs(u.norme_minkowski2() + C * C) / (C * C), 1e-14)

    def test_four_momentum_invariant_survives_boost(self):
        mass = 100.0
        p = quadrimpulsion_depuis_vitesse(mass, Vecteur3(0.75 * C, 0.1 * C, 0.0))
        boost = Vecteur3(0.4 * C, -0.05 * C, 0.0)
        boosted = transformer_quadrimpulsion_lorentz(p, boost)
        self.assertLess(abs(boosted.invariant_masse2() - mass * mass) / (mass * mass), 1e-13)
        recovered = transformer_quadrimpulsion_lorentz(boosted, -boost)
        self.assertLess(abs(recovered.energie - p.energie) / p.energie, 1e-13)
        self.assertLess((recovered.impulsion - p.impulsion).norm() / (mass * C), 1e-13)


if __name__ == "__main__":
    unittest.main()
