import unittest

from universe_sim.constants import SOLAR_MASS
from universe_sim.metrics import MetriqueKerrKerrSchild, MetriqueSchwarzschildKerrSchild
from universe_sim.services.horizons import detecter_franchissement_horizon, est_dans_horizon


class HorizonTests(unittest.TestCase):
    def test_schwarzschild_crossing_is_detected_once_when_entering(self):
        metric = MetriqueSchwarzschildKerrSchild(SOLAR_MASS)
        rs = metric.rayon_schwarzschild_m
        crossing = detecter_franchissement_horizon(
            metric,
            (0.0, 1.2 * rs, 0.0, 0.0),
            (1.0, 0.9 * rs, 0.0, 0.0),
        )
        self.assertIsNotNone(crossing)
        assert crossing is not None
        self.assertAlmostEqual(crossing.fraction_pas, 2.0 / 3.0, places=12)
        self.assertTrue(est_dans_horizon(metric, (1.0, 0.9 * rs, 0.0, 0.0)))
        self.assertIsNone(
            detecter_franchissement_horizon(
                metric,
                (1.0, 0.9 * rs, 0.0, 0.0),
                (2.0, 0.8 * rs, 0.0, 0.0),
            )
        )

    def test_kerr_uses_boyer_lindquist_horizon_radius(self):
        metric = MetriqueKerrKerrSchild(SOLAR_MASS, 0.8)
        rh = metric.rayon_horizon_externe_m
        self.assertFalse(est_dans_horizon(metric, (0.0, 1.5 * rh, 0.0, 0.0)))
        self.assertTrue(est_dans_horizon(metric, (0.0, 0.9 * rh, 0.0, 0.0)))


if __name__ == "__main__":
    unittest.main()
