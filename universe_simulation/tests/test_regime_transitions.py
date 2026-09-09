import unittest

from universe_sim.constants import C, SOLAR_MASS
from universe_sim.metrics import MetriqueMinkowski, MetriqueSchwarzschildKerrSchild
from universe_sim.relativistic_state import EtatCinematiqueRelativiste
from universe_sim.services.regime_transitions import (
    classique_vers_sr,
    sr_vers_classique,
    tangente_depuis_vitesse_coordonnees,
    vers_espace_temps_courbe,
)
from universe_sim.states import EtatMassique, EtatPhysique, EtatTranslationnel
from universe_sim.values import GrandeurPhysique, Instant, Vecteur3


class RegimeTransitionTests(unittest.TestCase):
    def test_classical_to_sr_preserves_coordinate_position_and_velocity(self):
        source = EtatPhysique(
            Instant(12.0),
            translation=EtatTranslationnel(Vecteur3(1.0, 2.0, 3.0), Vecteur3(0.5 * C, 0.0, 0.0)),
            massique=EtatMassique(GrandeurPhysique(1000.0, "kg")),
        )
        result = classique_vers_sr(source)
        self.assertIsNone(result.translation)
        self.assertIsNotNone(result.relativiste)
        self.assertEqual(result.position(), source.position())
        self.assertLess((result.vitesse() - source.vitesse()).norm() / C, 1e-14)

    def test_sr_to_classical_is_guarded_by_beta(self):
        state = EtatPhysique(
            Instant(0.0),
            massique=EtatMassique(GrandeurPhysique(1000.0, "kg")),
            relativiste=EtatCinematiqueRelativiste.depuis_vitesse(
                Vecteur3.zero(), Vecteur3(0.2 * C, 0.0, 0.0), 1000.0
            ),
        )
        with self.assertRaises(ValueError):
            sr_vers_classique(state)
        slow = EtatPhysique(
            Instant(0.0),
            massique=EtatMassique(GrandeurPhysique(1000.0, "kg")),
            relativiste=EtatCinematiqueRelativiste.depuis_vitesse(
                Vecteur3.zero(), Vecteur3(1e-4 * C, 0.0, 0.0), 1000.0
            ),
        )
        result = sr_vers_classique(slow)
        self.assertIsNotNone(result.translation)
        self.assertIsNone(result.relativiste)

    def test_minkowski_embedding_preserves_coordinate_velocity_and_normalization(self):
        metric = MetriqueMinkowski()
        state = EtatPhysique(
            Instant(3.0),
            massique=EtatMassique(GrandeurPhysique(10.0, "kg")),
            relativiste=EtatCinematiqueRelativiste.depuis_vitesse(
                Vecteur3(4.0, 5.0, 6.0), Vecteur3(0.7 * C, 0.0, 0.0), 10.0, 2.0
            ),
        )
        result = vers_espace_temps_courbe(state, metric)
        curved = result.espace_temps
        assert curved is not None
        self.assertIsNone(result.relativiste)
        self.assertAlmostEqual(curved.temps_propre_s, 2.0)
        self.assertLess((result.vitesse() - state.vitesse()).norm() / C, 1e-14)
        self.assertLess(abs(metric.contracter(curved.coordonnees_m, curved.tangente, curved.tangente) + 1.0), 1e-13)

    def test_non_timelike_coordinate_velocity_is_rejected_in_curved_chart(self):
        metric = MetriqueSchwarzschildKerrSchild(SOLAR_MASS)
        rs = metric.rayon_schwarzschild_m
        x = (0.0, 0.8 * rs, 0.0, 0.0)
        with self.assertRaises(ValueError):
            tangente_depuis_vitesse_coordonnees(metric, x, Vecteur3.zero())


if __name__ == "__main__":
    unittest.main()
