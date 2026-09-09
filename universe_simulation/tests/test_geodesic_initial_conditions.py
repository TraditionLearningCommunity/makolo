import unittest

from universe_sim.constants import SOLAR_MASS
from universe_sim.metrics import MetriqueMinkowski, MetriqueSchwarzschildKerrSchild
from universe_sim.simulation import TypeGeodesique, construire_tangente_normalisee


class GeodesicInitialConditionTests(unittest.TestCase):
    def test_timelike_minkowski_tangent_is_normalized(self):
        metric = MetriqueMinkowski()
        x = (0.0, 0.0, 0.0, 0.0)
        u = construire_tangente_normalisee(metric, x, (0.75, 0.0, 0.0), TypeGeodesique.TEMPORELLE)
        self.assertAlmostEqual(metric.contracter(x, u, u), -1.0, places=13)
        self.assertAlmostEqual(u[0], 1.25, places=13)

    def test_null_minkowski_tangent_is_null(self):
        metric = MetriqueMinkowski()
        x = (0.0, 0.0, 0.0, 0.0)
        k = construire_tangente_normalisee(metric, x, (1.0, 0.0, 0.0), TypeGeodesique.NULLE)
        self.assertAlmostEqual(metric.contracter(x, k, k), 0.0, places=13)
        self.assertAlmostEqual(k[0], 1.0, places=13)

    def test_ingoing_null_tangent_is_regular_at_horizon(self):
        metric = MetriqueSchwarzschildKerrSchild(SOLAR_MASS)
        rs = metric.rayon_schwarzschild_m
        x = (0.0, rs, 0.0, 0.0)
        k = construire_tangente_normalisee(metric, x, (-1.0, 0.0, 0.0), TypeGeodesique.NULLE)
        self.assertAlmostEqual(k[0], 1.0, places=10)
        self.assertLess(abs(metric.contracter(x, k, k)), 1e-12)


if __name__ == "__main__":
    unittest.main()
