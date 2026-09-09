import math
import unittest

from universe_sim.constants import C
from universe_sim.metrics import MetriqueMinkowski
from universe_sim.simulation.geodesic_integrator import EtatGeodesique, TypeGeodesique
from universe_sim.simulation.worldline_integrator import IntegrateurLigneUniversForceeRK4


class ForcedWorldlineTests(unittest.TestCase):
    def test_constant_proper_acceleration_matches_hyperbolic_motion(self):
        alpha = 9.80665
        metric = MetriqueMinkowski()

        def four_accel(_x, u):
            return (alpha * u[1], alpha * u[0], 0.0, 0.0)

        state = EtatGeodesique(
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
            type_geodesique=TypeGeodesique.TEMPORELLE,
        )
        integrator = IntegrateurLigneUniversForceeRK4(metric, four_accel, pas_relatif_derivation=1e-6)
        proper_time = 10.0 * 86_400.0
        total_lambda = C * proper_time
        steps = 200
        for _ in range(steps):
            integrator.avancer(state, total_lambda / steps)

        eta = alpha * proper_time / C
        expected_ct = C * C / alpha * math.sinh(eta)
        expected_x = C * C / alpha * (math.cosh(eta) - 1.0)
        self.assertLess(abs(state.coordonnees_m[0] - expected_ct) / max(1.0, expected_ct), 1e-10)
        self.assertLess(abs(state.coordonnees_m[1] - expected_x) / max(1.0, expected_x), 1e-9)
        self.assertLess(abs(state.tangente[0] - math.cosh(eta)), 1e-10)
        self.assertLess(abs(state.tangente[1] - math.sinh(eta)), 1e-10)
        self.assertLess(abs(state.norme(metric) + 1.0), 1e-9)

    def test_nonorthogonal_four_acceleration_is_rejected(self):
        metric = MetriqueMinkowski()
        state = EtatGeodesique(
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
            type_geodesique=TypeGeodesique.TEMPORELLE,
        )
        integrator = IntegrateurLigneUniversForceeRK4(metric, lambda _x, _u: (1.0, 0.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            integrator.avancer(state, 1.0)


if __name__ == "__main__":
    unittest.main()
