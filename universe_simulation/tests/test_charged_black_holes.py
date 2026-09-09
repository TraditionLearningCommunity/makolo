import math
import unittest

from universe_sim.constants import C, EPSILON_0, G, SOLAR_MASS
from universe_sim.metrics import MetriqueKerrKerrSchild, MetriqueKerrNewmanKerrSchild
from universe_sim.services.horizons import rayon_horizon_externe
from universe_sim.services.relativity import metrique_trou_noir_parametrique


def charge_pour_longueur_geometrique(q_m: float) -> float:
    return q_m * math.sqrt(4.0 * math.pi * EPSILON_0 * C**4 / G)


class ChargedBlackHoleMetricTests(unittest.TestCase):
    def test_zero_charge_kerr_newman_reduces_to_kerr_metric(self):
        kerr = MetriqueKerrKerrSchild(SOLAR_MASS, 0.6)
        kn = MetriqueKerrNewmanKerrSchild(SOLAR_MASS, 0.6, 0.0)
        x = (1.0e6, 30.0 * kerr.rayon_gravitationnel_m, 2.0e4, -5.0e3)
        gk = kerr.tenseur(x)
        gkn = kn.tenseur(x)
        error = max(abs(gk[i][j] - gkn[i][j]) for i in range(4) for j in range(4))
        self.assertLess(error, 1e-14)

    def test_charge_reduces_outer_horizon_radius(self):
        rg = G * SOLAR_MASS / C**2
        charge = charge_pour_longueur_geometrique(0.3 * rg)
        metric = MetriqueKerrNewmanKerrSchild(SOLAR_MASS, 0.0, charge)
        self.assertLess(metric.rayon_horizon_externe_m, 2.0 * rg)
        self.assertAlmostEqual(rayon_horizon_externe(metric), metric.rayon_horizon_externe_m)

    def test_over_extremal_charge_is_rejected(self):
        rg = G * SOLAR_MASS / C**2
        charge = charge_pour_longueur_geometrique(1.1 * rg)
        with self.assertRaises(ValueError):
            MetriqueKerrNewmanKerrSchild(SOLAR_MASS, 0.0, charge)

    def test_metric_selector_uses_kerr_newman_when_charge_is_nonzero(self):
        rg = G * SOLAR_MASS / C**2
        charge = charge_pour_longueur_geometrique(0.1 * rg)
        metric = metrique_trou_noir_parametrique(SOLAR_MASS, 0.4, charge)
        self.assertIsInstance(metric, MetriqueKerrNewmanKerrSchild)


if __name__ == "__main__":
    unittest.main()
