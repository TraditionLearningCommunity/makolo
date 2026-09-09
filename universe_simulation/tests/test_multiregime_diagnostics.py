import unittest

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import C
from universe_sim.relativistic_state import EtatCinematiqueRelativiste
from universe_sim.simulation.clock import HorlogeSimulation
from universe_sim.simulation.configuration import ConfigurationPhysique
from universe_sim.simulation.multiregime import EvolutionSRCorps, SimulationMultiRegime
from universe_sim.states import EtatMassique, EtatPhysique
from universe_sim.systems import Univers
from universe_sim.values import Duree, GrandeurPhysique, Instant, Vecteur3


class MultiRegimeDiagnosticsTests(unittest.TestCase):
    def test_mixed_relativistic_run_records_snapshots_and_regime_diagnostics(self):
        body = CorpsPhysique(
            "ship",
            EtatPhysique(
                Instant(0.0),
                massique=EtatMassique(GrandeurPhysique(1000.0, "kg")),
                relativiste=EtatCinematiqueRelativiste.depuis_vitesse(
                    Vecteur3.zero(), Vecteur3(0.8 * C, 0.0, 0.0), 1000.0
                ),
            ),
        )
        config = ConfigurationPhysique(conserver_historique=True, enregistrer_tous_les_n_pas=1)
        sim = SimulationMultiRegime(
            Univers("rel", corps_physiques=[body]),
            HorlogeSimulation(Instant(0.0), Duree(2.0)),
            config,
        )
        sim.ajouter_evolution(EvolutionSRCorps(body.id))
        sim.avancer()

        self.assertEqual(len(sim.snapshots), 1)
        self.assertEqual(sim.snapshots[0].instant.seconds, 2.0)
        diagnostic = sim.diagnostic()
        self.assertIsNone(diagnostic["energie_mecanique"])
        self.assertEqual(diagnostic["regimes"], {"relativiste_special": 1})
        self.assertGreater(diagnostic["gamma_max_sr"], 1.0)
        self.assertLess(diagnostic["temps_propre_max_s"], 2.0)

    def test_snapshots_respect_recording_cadence(self):
        body = CorpsPhysique(
            "ship",
            EtatPhysique(
                Instant(0.0),
                massique=EtatMassique(GrandeurPhysique(1000.0, "kg")),
                relativiste=EtatCinematiqueRelativiste(),
            ),
        )
        config = ConfigurationPhysique(conserver_historique=True, enregistrer_tous_les_n_pas=2)
        sim = SimulationMultiRegime(
            Univers("rel", corps_physiques=[body]),
            HorlogeSimulation(Instant(0.0), Duree(1.0)),
            config,
        )
        sim.ajouter_evolution(EvolutionSRCorps(body.id))
        sim.avancer()
        self.assertEqual(len(sim.snapshots), 0)
        sim.avancer()
        self.assertEqual(len(sim.snapshots), 1)
        self.assertEqual(sim.snapshots[0].instant.seconds, 2.0)


if __name__ == "__main__":
    unittest.main()
