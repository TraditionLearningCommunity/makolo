import unittest

from universe_sim.constants import C
from universe_sim.metrics import MetriqueMinkowski
from universe_sim.simulation.coordinate_time import avancer_jusqua_temps_coordonne
from universe_sim.simulation.geodesic_integrator import EtatGeodesique, IntegrateurGeodesiqueRK4, TypeGeodesique


class CoordinateTimeSyncTests(unittest.TestCase):
    def test_timelike_minkowski_worldline_lands_on_exact_coordinate_time(self):
        beta = 0.8
        gamma = 1.0 / (1.0 - beta * beta) ** 0.5
        state = EtatGeodesique(
            (0.0, 0.0, 0.0, 0.0),
            (gamma, gamma * beta, 0.0, 0.0),
            type_geodesique=TypeGeodesique.TEMPORELLE,
        )
        affine = avancer_jusqua_temps_coordonne(
            IntegrateurGeodesiqueRK4(MetriqueMinkowski()),
            state,
            10.0,
        )
        self.assertLess(abs(state.coordonnees_m[0] - 10.0 * C), 1e-5)
        self.assertLess(abs(state.coordonnees_m[1] - 0.8 * C * 10.0), 1e-5)
        self.assertLess(abs(affine - C * 10.0 / gamma), 1e-5)

    def test_null_minkowski_sync_supports_multiple_affine_substeps(self):
        state = EtatGeodesique(
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 1.0, 0.0, 0.0),
            type_geodesique=TypeGeodesique.NULLE,
        )
        avancer_jusqua_temps_coordonne(
            IntegrateurGeodesiqueRK4(MetriqueMinkowski()),
            state,
            2.0,
            dlambda_max_m=0.3 * C,
        )
        self.assertLess(abs(state.coordonnees_m[0] - 2.0 * C), 1e-5)
        self.assertLess(abs(state.coordonnees_m[1] - 2.0 * C), 1e-5)


if __name__ == "__main__":
    unittest.main()
