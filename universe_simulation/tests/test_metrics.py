import unittest

from universe_sim.constants import C, G, SOLAR_MASS
from universe_sim.metrics import MetriqueFLRWPlate, MetriqueKerrKerrSchild, MetriqueSchwarzschildKerrSchild


class MetricTests(unittest.TestCase):
    def test_schwarzschild_kerr_schild_is_finite_at_horizon(self):
        metric = MetriqueSchwarzschildKerrSchild(SOLAR_MASS)
        rs = metric.rayon_schwarzschild_m
        g = metric.tenseur((0.0, rs, 0.0, 0.0))
        for row in g:
            for value in row:
                self.assertTrue(abs(value) < 10.0)
        self.assertAlmostEqual(g[0][0], 0.0, places=12)

    def test_schwarzschild_tends_to_minkowski_far_away(self):
        metric = MetriqueSchwarzschildKerrSchild(SOLAR_MASS)
        r = 1e9 * metric.rayon_schwarzschild_m
        g = metric.tenseur((0.0, r, 0.0, 0.0))
        self.assertLess(abs(g[0][0] + 1.0), 2e-9)
        self.assertLess(abs(g[1][1] - 1.0), 2e-9)

    def test_zero_spin_kerr_matches_schwarzschild(self):
        schwarzschild = MetriqueSchwarzschildKerrSchild(SOLAR_MASS)
        kerr = MetriqueKerrKerrSchild(SOLAR_MASS, 0.0)
        x = (1.2e6, 20.0 * schwarzschild.rayon_schwarzschild_m, 1.3e4, -7e3)
        gs = schwarzschild.tenseur(x)
        gk = kerr.tenseur(x)
        error = max(abs(gs[i][j] - gk[i][j]) for i in range(4) for j in range(4))
        self.assertLess(error, 1e-14)

    def test_kerr_horizon_shrinks_with_spin_and_ergosphere_is_outside(self):
        kerr = MetriqueKerrKerrSchild(SOLAR_MASS, 0.9)
        schwarzschild_radius = 2.0 * G * SOLAR_MASS / (C * C)
        self.assertLess(kerr.rayon_horizon_externe_m, schwarzschild_radius)
        self.assertGreaterEqual(
            kerr.rayon_ergosphere_externe_m(1.5707963267948966),
            kerr.rayon_horizon_externe_m,
        )

    def test_superextremal_kerr_is_rejected(self):
        with self.assertRaises(ValueError):
            MetriqueKerrKerrSchild(SOLAR_MASS, 1.01)

    def test_flat_flrw_uses_prescribed_scale_factor(self):
        metric = MetriqueFLRWPlate(lambda _t: 2.0)
        g = metric.tenseur((0.0, 0.0, 0.0, 0.0))
        self.assertEqual(g[0][0], -1.0)
        self.assertEqual(g[1][1], 4.0)


if __name__ == "__main__":
    unittest.main()
