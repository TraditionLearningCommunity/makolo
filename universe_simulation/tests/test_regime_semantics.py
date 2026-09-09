import unittest

from universe_sim.constants import C
from universe_sim.regime_selector import diagnostiquer_regime
from universe_sim.regimes import RegimeDynamique
from universe_sim.values import Vecteur3


class RegimeSemanticsTests(unittest.TestCase):
    def test_geodesic_name_is_backward_compatible_alias_of_general_relativity(self):
        self.assertIs(RegimeDynamique.GEODESIQUE, RegimeDynamique.RELATIVISTE_GENERAL)
        self.assertEqual(RegimeDynamique.GEODESIQUE.value, "relativiste_general")
        self.assertIs(RegimeDynamique("geodesique"), RegimeDynamique.RELATIVISTE_GENERAL)

    def test_selector_reports_general_relativity_for_curved_relativistic_motion(self):
        diagnostic = diagnostiquer_regime(Vecteur3(0.8 * C, 0.0, 0.0), -1e-4 * C * C)
        self.assertIs(diagnostic.regime, RegimeDynamique.RELATIVISTE_GENERAL)

    def test_legacy_force_geodesic_argument_still_selects_general_relativity(self):
        diagnostic = diagnostiquer_regime(Vecteur3.zero(), 0.0, imposer_geodesique=True)
        self.assertIs(diagnostic.regime, RegimeDynamique.RELATIVISTE_GENERAL)


if __name__ == "__main__":
    unittest.main()
