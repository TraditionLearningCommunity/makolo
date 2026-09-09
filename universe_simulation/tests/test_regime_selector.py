import unittest

from universe_sim.constants import C
from universe_sim.regime_selector import SeuilsSelectionRegime, diagnostiquer_regime
from universe_sim.regimes import RegimeDynamique
from universe_sim.values import Vecteur3


class RegimeSelectorTests(unittest.TestCase):
    def test_slow_weak_field_is_classical(self):
        diagnostic = diagnostiquer_regime(Vecteur3(1000.0, 0.0, 0.0), -1e6)
        self.assertEqual(diagnostic.regime, RegimeDynamique.CLASSIQUE)

    def test_high_speed_weak_field_is_special_relativity(self):
        diagnostic = diagnostiquer_regime(Vecteur3(0.8 * C, 0.0, 0.0), -1e6)
        self.assertEqual(diagnostic.regime, RegimeDynamique.RELATIVISTE_SPECIAL)

    def test_high_speed_with_non_negligible_gravity_uses_curved_spacetime(self):
        diagnostic = diagnostiquer_regime(Vecteur3(0.8 * C, 0.0, 0.0), -1e-4 * C * C)
        self.assertEqual(diagnostic.regime, RegimeDynamique.GEODESIQUE)

    def test_strong_field_is_geodesic_even_at_low_speed(self):
        diagnostic = diagnostiquer_regime(Vecteur3(1000.0, 0.0, 0.0), -0.05 * C * C)
        self.assertEqual(diagnostic.regime, RegimeDynamique.GEODESIQUE)

    def test_precision_can_promote_weak_correction_to_1pn(self):
        thresholds = SeuilsSelectionRegime(precision_newtonienne=1e-10)
        diagnostic = diagnostiquer_regime(
            Vecteur3(1e-4 * C, 0.0, 0.0),
            -1e-9 * C * C,
            thresholds,
        )
        self.assertEqual(diagnostic.regime, RegimeDynamique.POST_NEWTONIEN_1PN)

    def test_scale_alone_is_not_a_selection_input(self):
        local = diagnostiquer_regime(Vecteur3(0.2 * C, 0.0, 0.0), 0.0)
        galactic = diagnostiquer_regime(Vecteur3(0.2 * C, 0.0, 0.0), 0.0)
        self.assertEqual(local.regime, galactic.regime)


if __name__ == "__main__":
    unittest.main()
