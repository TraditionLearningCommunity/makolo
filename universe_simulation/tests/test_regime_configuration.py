import unittest

from universe_sim.regimes import NiveauActiviteCalcul, RegimeDynamique
from universe_sim.simulation.configuration import ConfigurationPhysique


class RegimeConfigurationTests(unittest.TestCase):
    def test_existing_bodies_remain_classical_by_default(self):
        config = ConfigurationPhysique()
        self.assertEqual(config.regime_pour("body"), RegimeDynamique.CLASSIQUE)
        self.assertEqual(config.niveau_activite_pour("body"), NiveauActiviteCalcul.ACTIVE)

    def test_per_body_regimes_can_coexist(self):
        config = ConfigurationPhysique()
        config.definir_regime("planet", RegimeDynamique.CLASSIQUE)
        config.definir_regime("ship", RegimeDynamique.RELATIVISTE_SPECIAL)
        config.definir_regime("probe-bh", RegimeDynamique.GEODESIQUE)
        self.assertEqual(config.regime_pour("planet"), RegimeDynamique.CLASSIQUE)
        self.assertEqual(config.regime_pour("ship"), RegimeDynamique.RELATIVISTE_SPECIAL)
        self.assertEqual(config.regime_pour("probe-bh"), RegimeDynamique.GEODESIQUE)


if __name__ == "__main__":
    unittest.main()
