import unittest

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import C, SOLAR_MASS
from universe_sim.metrics import MetriqueSchwarzschildKerrSchild
from universe_sim.relativistic_state import EtatSpatioTemporelRelativiste, TypeCourbeCausale
from universe_sim.simulation.clock import HorlogeSimulation
from universe_sim.simulation.configuration import ConfigurationPhysique
from universe_sim.simulation.multiregime import EvolutionGeodesiqueCorps, SimulationMultiRegime
from universe_sim.states import EtatPhysique
from universe_sim.systems import Univers
from universe_sim.values import Duree, Instant


class EscapingAffineIntegrator:
    def __init__(self, metric, exit_radius):
        self.metrique = metric
        self.exit_radius = exit_radius
        self.nom = "deliberately invalid escaping integrator"

    def avancer(self, state, dlambda_m):
        state.coordonnees_m = (
            state.coordonnees_m[0] + state.tangente[0] * dlambda_m,
            self.exit_radius,
            0.0,
            0.0,
        )
        state.parametre_affine_m += dlambda_m


class HorizonCausalityGuardTests(unittest.TestCase):
    def test_numerical_reemergence_from_inside_horizon_is_rejected_and_rolled_back(self):
        metric = MetriqueSchwarzschildKerrSchild(SOLAR_MASS)
        rs = metric.rayon_schwarzschild_m
        body = CorpsPhysique(
            "inside",
            EtatPhysique(
                Instant(0.0),
                espace_temps=EtatSpatioTemporelRelativiste(
                    (0.0, 0.8 * rs, 0.0, 0.0),
                    (1.0, -1.0, 0.0, 0.0),
                    type_causal=TypeCourbeCausale.NULLE,
                ),
            ),
        )
        original = body.etat().espace_temps.coordonnees_m
        simulation = SimulationMultiRegime(
            Univers("bh", corps_physiques=[body]),
            HorlogeSimulation(Instant(0.0), Duree(1e-6)),
            ConfigurationPhysique(conserver_historique=False),
        )
        simulation.ajouter_evolution(
            EvolutionGeodesiqueCorps(body.id, EscapingAffineIntegrator(metric, 1.2 * rs))
        )
        with self.assertRaises(ArithmeticError):
            simulation.avancer()
        self.assertEqual(body.etat().espace_temps.coordonnees_m, original)
        self.assertEqual(simulation.horloge.instant_courant.seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
