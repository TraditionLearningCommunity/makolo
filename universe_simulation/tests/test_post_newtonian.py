import unittest

from universe_sim.constants import AU, C, EARTH_MASS, G, SOLAR_MASS
from universe_sim.services.post_newtonian import acceleration_relative_1pn, repartir_acceleration_relative
from universe_sim.values import Vecteur3


class PostNewtonianTests(unittest.TestCase):
    def test_solar_system_1pn_is_small_correction(self):
        r = Vecteur3(AU, 0.0, 0.0)
        v = Vecteur3(0.0, 29_780.0, 0.0)
        full = acceleration_relative_1pn(r, v, SOLAR_MASS, EARTH_MASS, True)
        newton = Vecteur3(-G * (SOLAR_MASS + EARTH_MASS) / (AU * AU), 0.0, 0.0)
        correction = (full - newton).norm()
        self.assertGreater(correction, 0.0)
        self.assertLess(correction / newton.norm(), 1e-6)

    def test_barycentric_split_preserves_relative_acceleration(self):
        relative = Vecteur3(-3.0, 2.0, 0.5)
        m1, m2 = 5.0, 2.0
        a1, a2 = repartir_acceleration_relative(relative, m1, m2)
        self.assertLess(((a2 - a1) - relative).norm(), 1e-14)
        self.assertLess((a1 * m1 + a2 * m2).norm(), 1e-14)

    def test_zero_separation_is_rejected(self):
        with self.assertRaises(ValueError):
            acceleration_relative_1pn(Vecteur3.zero(), Vecteur3.zero(), 1.0, 1.0)

    def test_test_particle_circular_correction_has_expected_order(self):
        rmag = 20.0 * G * SOLAR_MASS / (C * C)
        mu = G * SOLAR_MASS
        vcirc = (mu / rmag) ** 0.5
        correction = acceleration_relative_1pn(
            Vecteur3(rmag, 0.0, 0.0),
            Vecteur3(0.0, vcirc, 0.0),
            SOLAR_MASS,
            1.0,
            False,
        )
        expected = 3.0 * mu * mu / (C * C * rmag**3)
        self.assertLess(abs(correction.x - expected) / expected, 1e-12)


if __name__ == "__main__":
    unittest.main()
