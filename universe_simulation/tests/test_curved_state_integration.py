import unittest

from universe_sim.constants import C
from universe_sim.relativistic_state import EtatSpatioTemporelRelativiste, TypeCourbeCausale
from universe_sim.states import EtatPhysique, EtatTranslationnel
from universe_sim.values import Instant, Vecteur3


class CurvedStateIntegrationTests(unittest.TestCase):
    def test_timelike_curved_state_exposes_coordinate_position_velocity_and_time(self):
        curved = EtatSpatioTemporelRelativiste(
            (2.0 * C, 10.0, 20.0, 30.0),
            (2.0, 0.5, 0.0, 0.0),
            120.0,
            TypeCourbeCausale.TEMPORELLE,
            0.4,
        )
        state = EtatPhysique(Instant(2.0), espace_temps=curved)
        self.assertEqual(state.position(), Vecteur3(10.0, 20.0, 30.0))
        velocity = state.vitesse()
        assert velocity is not None
        self.assertAlmostEqual(velocity.x, 0.25 * C)
        self.assertAlmostEqual(curved.temps_coordonne_s(), 2.0)

    def test_null_state_has_no_proper_time(self):
        curved = EtatSpatioTemporelRelativiste(
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 1.0, 0.0, 0.0),
            type_causal=TypeCourbeCausale.NULLE,
        )
        self.assertIsNone(curved.temps_propre_s)

    def test_flat_and_curved_kinematics_cannot_coexist(self):
        curved = EtatSpatioTemporelRelativiste((0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            EtatPhysique(Instant(0.0), translation=EtatTranslationnel(), espace_temps=curved)


if __name__ == "__main__":
    unittest.main()
