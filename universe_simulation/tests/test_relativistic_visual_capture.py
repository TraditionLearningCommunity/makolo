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
from universe_sim.visuals.capture import capturer_sequence


class RelativisticVisualCaptureTests(unittest.TestCase):
    def test_sr_body_is_captured_without_classical_translation(self):
        body = CorpsPhysique(
            "ship",
            EtatPhysique(
                Instant(0.0),
                massique=EtatMassique(GrandeurPhysique(1000.0, "kg")),
                relativiste=EtatCinematiqueRelativiste.depuis_vitesse(
                    Vecteur3.zero(), Vecteur3(0.5 * C, 0.0, 0.0), 1000.0
                ),
            ),
        )
        sim = SimulationMultiRegime(
            Univers("u", corps_physiques=[body]),
            HorlogeSimulation(Instant(0.0), Duree(1.0)),
            ConfigurationPhysique(),
        )
        sim.ajouter_evolution(EvolutionSRCorps(body.id))
        seq = capturer_sequence(sim, 2, 3)
        xs = [frame.positions[body.id].x for frame in seq.frames]
        self.assertEqual(len(xs), 3)
        self.assertAlmostEqual(xs[0], 0.0)
        self.assertLess(abs(xs[1] - 0.5 * C), 1e-6)
        self.assertLess(abs(xs[2] - C), 1e-6)


if __name__ == "__main__":
    unittest.main()
