import unittest

from universe_sim.constants import SOLAR_MASS
from universe_sim.metrics import MetriqueMinkowski, MetriqueSchwarzschildKerrSchild
from universe_sim.services.differential_geometry import symboles_christoffel
from universe_sim.simulation import EtatGeodesique, IntegrateurGeodesiqueRK4, TypeGeodesique


class GeodesicTests(unittest.TestCase):
    def test_minkowski_christoffels_are_zero(self):
        gamma = symboles_christoffel(MetriqueMinkowski(), (0.0, 1.0, 2.0, 3.0))
        maximum = max(abs(gamma[m][a][b]) for m in range(4) for a in range(4) for b in range(4))
        self.assertEqual(maximum, 0.0)

    def test_minkowski_geodesic_is_linear(self):
        metric = MetriqueMinkowski()
        state = EtatGeodesique((0.0, 0.0, 0.0, 0.0), (1.25, 0.2, -0.1, 0.05))
        integrator = IntegrateurGeodesiqueRK4(metric)
        integrator.avancer(state, 1000.0)
        expected = (1250.0, 200.0, -100.0, 50.0)
        self.assertLess(max(abs(state.coordonnees_m[i] - expected[i]) for i in range(4)), 1e-10)
        self.assertEqual(state.tangente, (1.25, 0.2, -0.1, 0.05))

    def test_ingoing_null_geodesic_crosses_schwarzschild_horizon(self):
        metric = MetriqueSchwarzschildKerrSchild(SOLAR_MASS)
        rs = metric.rayon_schwarzschild_m
        state = EtatGeodesique(
            (0.0, 1.2 * rs, 0.0, 0.0),
            (1.0, -1.0, 0.0, 0.0),
            type_geodesique=TypeGeodesique.NULLE,
        )
        self.assertLess(abs(state.norme(metric)), 1e-12)
        integrator = IntegrateurGeodesiqueRK4(
            metric,
            pas_relatif_derivation=2e-6,
            pas_absolu_derivation_m=1e-4,
        )
        integrator.avancer(state, 0.35 * rs)
        self.assertLess(state.coordonnees_m[1], rs)
        self.assertGreater(state.coordonnees_m[1], 0.0)
        self.assertLess(abs(state.norme(metric)), 1e-6)


if __name__ == "__main__":
    unittest.main()
