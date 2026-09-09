import unittest

from universe_sim.regimes import NiveauActiviteCalcul, PolitiqueDynamique, RegimeDynamique, TypeBackendEtat


class DynamicsRegimeTests(unittest.TestCase):
    def test_default_policy_preserves_classical_behavior(self):
        policy = PolitiqueDynamique()
        self.assertEqual(policy.regime_par_defaut, RegimeDynamique.CLASSIQUE)
        self.assertFalse(policy.selection_automatique)

    def test_activity_levels_are_computational_not_physical_types(self):
        self.assertEqual(NiveauActiviteCalcul.ACTIVE.value, "active")
        self.assertEqual(NiveauActiviteCalcul.AGGREGATED.value, "aggregated")
        self.assertEqual(TypeBackendEtat.OBJET.value, "object")

    def test_precision_must_be_positive(self):
        with self.assertRaises(ValueError):
            PolitiqueDynamique(precision_relative_cible=0.0)


if __name__ == "__main__":
    unittest.main()
