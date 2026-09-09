import unittest

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import AU, EARTH_MASS, G, SOLAR_MASS
from universe_sim.regimes import RegimeDynamique
from universe_sim.simulation import Evolution1PNDeuxCorps, HorlogeSimulation, SimulationMultiRegime
from universe_sim.simulation.configuration import ConfigurationPhysique
from universe_sim.states import EtatMassique, EtatPhysique, EtatTranslationnel
from universe_sim.systems import Univers
from universe_sim.values import Duree, GrandeurPhysique, Instant, Vecteur3


class MultiRegime1PNTests(unittest.TestCase):
    def test_1pn_pair_is_owned_and_advanced_as_one_regime(self):
        total = SOLAR_MASS + EARTH_MASS
        radius = AU
        omega = (G * total / radius**3) ** 0.5
        r1 = radius * EARTH_MASS / total
        r2 = radius * SOLAR_MASS / total
        sun = CorpsPhysique(
            "sun",
            EtatPhysique(
                Instant(0.0),
                translation=EtatTranslationnel(Vecteur3(-r1, 0.0, 0.0), Vecteur3(0.0, -omega * r1, 0.0)),
                massique=EtatMassique(GrandeurPhysique(SOLAR_MASS, "kg")),
            ),
        )
        earth = CorpsPhysique(
            "earth",
            EtatPhysique(
                Instant(0.0),
                translation=EtatTranslationnel(Vecteur3(r2, 0.0, 0.0), Vecteur3(0.0, omega * r2, 0.0)),
                massique=EtatMassique(GrandeurPhysique(EARTH_MASS, "kg")),
            ),
        )
        universe = Univers("pn", corps_physiques=[sun, earth])
        configuration = ConfigurationPhysique()
        simulation = SimulationMultiRegime(
            universe,
            HorlogeSimulation(Instant(0.0), Duree(3600.0)),
            configuration,
        )
        simulation.ajouter_evolution(Evolution1PNDeuxCorps(sun.id, earth.id))
        simulation.avancer()
        self.assertEqual(configuration.regime_pour(sun.id), RegimeDynamique.POST_NEWTONIEN_1PN)
        self.assertEqual(configuration.regime_pour(earth.id), RegimeDynamique.POST_NEWTONIEN_1PN)
        self.assertEqual(sun.etat().instant.seconds, 3600.0)
        self.assertEqual(earth.etat().instant.seconds, 3600.0)
        self.assertNotEqual(earth.etat().translation.position, Vecteur3(r2, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
