import unittest

from universe_sim.constants import C
from universe_sim.relativistic_state import EtatCinematiqueRelativiste
from universe_sim.states import EtatMassique, EtatPhysique, EtatTranslationnel
from universe_sim.values import GrandeurPhysique, Instant, Vecteur3


class StateIntegrationTests(unittest.TestCase):
    def test_classical_state_remains_unchanged(self):
        state = EtatPhysique(
            Instant(0.0),
            translation=EtatTranslationnel(Vecteur3(1.0, 2.0, 3.0), Vecteur3(4.0, 5.0, 6.0)),
            massique=EtatMassique(GrandeurPhysique(10.0, "kg")),
        )
        self.assertEqual(state.position(), Vecteur3(1.0, 2.0, 3.0))
        self.assertEqual(state.vitesse(), Vecteur3(4.0, 5.0, 6.0))
        self.assertIsNot(state.copier(), state)

    def test_relativistic_state_derives_velocity_from_momentum(self):
        relativistic = EtatCinematiqueRelativiste.depuis_vitesse(
            Vecteur3(1.0, 0.0, 0.0), Vecteur3(0.9 * C, 0.0, 0.0), 1000.0
        )
        state = EtatPhysique(
            Instant(0.0),
            massique=EtatMassique(GrandeurPhysique(1000.0, "kg")),
            relativiste=relativistic,
        )
        self.assertEqual(state.position(), Vecteur3(1.0, 0.0, 0.0))
        velocity = state.vitesse()
        assert velocity is not None
        self.assertLess(abs(velocity.x - 0.9 * C) / C, 1e-14)
        copied = state.copier()
        self.assertEqual(copied.relativiste, state.relativiste)
        self.assertIsNot(copied.relativiste, state.relativiste)

    def test_two_kinematic_sources_are_rejected(self):
        with self.assertRaises(ValueError):
            EtatPhysique(
                Instant(0.0),
                translation=EtatTranslationnel(),
                relativiste=EtatCinematiqueRelativiste(),
            )


if __name__ == "__main__":
    unittest.main()
