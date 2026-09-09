import unittest

from universe_sim.constants import SOLAR_MASS
from universe_sim.metrics import MetriqueMinkowski, MetriqueSchwarzschildKerrSchild
from universe_sim.simulation import EtatGeodesique, IntegrateurGeodesiqueAdaptatif, TypeGeodesique


class AdaptiveGeodesicTests(unittest.TestCase):
    def test_minkowski_linear_geodesic_needs_no_real_refinement(self):
        metric = MetriqueMinkowski()
        state = EtatGeodesique((0.0, 0.0, 0.0, 0.0), (1.25, 0.2, -0.1, 0.05))
        solver = IntegrateurGeodesiqueAdaptatif(metric, tolerance_relative=1e-12, tolerance_absolue=1e-10)
        solver.avancer(state, 1000.0)
        expected = (1250.0, 200.0, -100.0, 50.0)
        self.assertLess(max(abs(state.coordonnees_m[i] - expected[i]) for i in range(4)), 1e-9)
        self.assertEqual(solver.dernier_nombre_sous_pas, 2)

    def test_adaptive_solver_crosses_schwarzschild_horizon_and_preserves_null_character(self):
        metric = MetriqueSchwarzschildKerrSchild(SOLAR_MASS)
        rs = metric.rayon_schwarzschild_m
        state = EtatGeodesique(
            (0.0, 1.2 * rs, 0.0, 0.0),
            (1.0, -1.0, 0.0, 0.0),
            type_geodesique=TypeGeodesique.NULLE,
        )
        solver = IntegrateurGeodesiqueAdaptatif(
            metric,
            tolerance_relative=1e-8,
            tolerance_absolue=1e-7,
            max_subdivisions=16,
            pas_relatif_derivation=2e-6,
            pas_absolu_derivation_m=1e-4,
        )
        solver.avancer(state, 0.35 * rs)
        self.assertLess(state.coordonnees_m[1], rs)
        self.assertGreater(state.coordonnees_m[1], 0.0)
        self.assertLess(abs(state.norme(metric)), 1e-5)
        self.assertGreaterEqual(solver.dernier_nombre_sous_pas, 2)

    def test_invalid_tolerance_is_rejected(self):
        with self.assertRaises(ValueError):
            IntegrateurGeodesiqueAdaptatif(MetriqueMinkowski(), tolerance_relative=0.0)


if __name__ == "__main__":
    unittest.main()
