import unittest

from universe_sim.constants import C, SOLAR_MASS
from universe_sim.metrics import MetriqueMinkowski, MetriqueSchwarzschildKerrSchild
from universe_sim.services.local_frames import (
    construire_tetrade_observateur,
    construire_tetrade_observateur_stationnaire,
)


class LocalObserverFrameTests(unittest.TestCase):
    def test_moving_minkowski_observer_measures_relative_speed(self):
        metric = MetriqueMinkowski()
        x = (0.0, 0.0, 0.0, 0.0)
        beta = 0.6
        gamma = 1.0 / (1.0 - beta * beta) ** 0.5
        observer = (gamma, gamma * beta, 0.0, 0.0)
        tetrad = construire_tetrade_observateur(metric, x, observer)
        self.assertTrue(tetrad.verifier(metric, x))
        velocity = tetrad.vitesse_locale(metric, x, (1.0, 0.0, 0.0, 0.0))
        self.assertLess(abs(velocity[0] + beta * C) / C, 1e-13)
        self.assertLess(abs(tetrad.gamma_local(metric, x, (1.0, 0.0, 0.0, 0.0)) - gamma), 1e-13)

    def test_every_local_observer_measures_light_at_c(self):
        metric = MetriqueMinkowski()
        x = (0.0, 0.0, 0.0, 0.0)
        beta = 0.75
        gamma = 1.0 / (1.0 - beta * beta) ** 0.5
        tetrad = construire_tetrade_observateur(metric, x, (gamma, gamma * beta, 0.0, 0.0))
        velocity = tetrad.vitesse_locale(metric, x, (1.0, 1.0, 0.0, 0.0))
        speed = (velocity[0] ** 2 + velocity[1] ** 2 + velocity[2] ** 2) ** 0.5
        self.assertLess(abs(speed - C) / C, 1e-13)

    def test_stationary_schwarzschild_observer_exists_outside_horizon_only(self):
        metric = MetriqueSchwarzschildKerrSchild(SOLAR_MASS)
        rs = metric.rayon_schwarzschild_m
        outside = (0.0, 3.0 * rs, 0.0, 0.0)
        tetrad = construire_tetrade_observateur_stationnaire(metric, outside)
        self.assertTrue(tetrad.verifier(metric, outside, tolerance=1e-8))
        with self.assertRaises(ValueError):
            construire_tetrade_observateur_stationnaire(metric, (0.0, rs, 0.0, 0.0))
        with self.assertRaises(ValueError):
            construire_tetrade_observateur_stationnaire(metric, (0.0, 0.8 * rs, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
