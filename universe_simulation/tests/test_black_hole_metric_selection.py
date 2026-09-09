import unittest

from universe_sim.constants import SOLAR_MASS
from universe_sim.metrics import MetriqueKerrKerrSchild, MetriqueSchwarzschildKerrSchild
from universe_sim.services.relativity import metrique_trou_noir_parametrique


class BlackHoleMetricSelectionTests(unittest.TestCase):
    def test_nonrotating_black_hole_selects_schwarzschild(self):
        metric = metrique_trou_noir_parametrique(10.0 * SOLAR_MASS, 0.0)
        self.assertIsInstance(metric, MetriqueSchwarzschildKerrSchild)

    def test_rotating_black_hole_selects_kerr(self):
        metric = metrique_trou_noir_parametrique(10.0 * SOLAR_MASS, 0.7)
        self.assertIsInstance(metric, MetriqueKerrKerrSchild)
        assert isinstance(metric, MetriqueKerrKerrSchild)
        self.assertAlmostEqual(metric.spin_dimensionnel, 0.7)


if __name__ == "__main__":
    unittest.main()
