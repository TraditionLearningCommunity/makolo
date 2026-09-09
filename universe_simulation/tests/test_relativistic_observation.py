import unittest

from universe_sim.metrics import MetriqueMinkowski
from universe_sim.services.relativistic_observation import (
    decalage_cosmologique_flrw,
    decalage_vers_rouge_depuis_rapport,
    facteur_doppler_longitudinal_sr,
    frequence_photon_mesuree_relative,
)


class RelativisticObservationTests(unittest.TestCase):
    def test_longitudinal_doppler_matches_four_vector_measurement(self):
        metric = MetriqueMinkowski()
        beta = 0.6
        gamma = 1.0 / (1.0 - beta * beta) ** 0.5
        photon = (1.0, 1.0, 0.0, 0.0)
        stationary = (1.0, 0.0, 0.0, 0.0)
        receding = (gamma, gamma * beta, 0.0, 0.0)
        emitted = frequence_photon_mesuree_relative(metric, (0.0, 0.0, 0.0, 0.0), photon, stationary)
        received = frequence_photon_mesuree_relative(metric, (1.0, 1.0, 0.0, 0.0), photon, receding)
        ratio = received / emitted
        self.assertAlmostEqual(ratio, facteur_doppler_longitudinal_sr(beta), places=13)
        self.assertAlmostEqual(decalage_vers_rouge_depuis_rapport(ratio), 1.0, places=13)

    def test_flrw_redshift_uses_scale_factor_ratio(self):
        self.assertAlmostEqual(decalage_cosmologique_flrw(0.5, 1.0), 1.0)

    def test_invalid_causal_frequency_is_rejected(self):
        with self.assertRaises(ValueError):
            frequence_photon_mesuree_relative(
                MetriqueMinkowski(),
                (0.0, 0.0, 0.0, 0.0),
                (-1.0, 1.0, 0.0, 0.0),
                (1.0, 0.0, 0.0, 0.0),
            )


if __name__ == "__main__":
    unittest.main()
