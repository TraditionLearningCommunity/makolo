import unittest

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import C
from universe_sim.metrics import MetriqueMinkowski
from universe_sim.relativistic_state import EtatCinematiqueRelativiste, EtatSpatioTemporelRelativiste, TypeCourbeCausale
from universe_sim.simulation import (
    EvolutionClassiqueGroupe,
    EvolutionGeodesiqueCorps,
    EvolutionSRCorps,
    HorlogeSimulation,
    IntegrateurGeodesiqueRK4,
    SimulationMultiRegime,
)
from universe_sim.simulation.configuration import ConfigurationPhysique
from universe_sim.states import EtatMassique, EtatPhysique, EtatTranslationnel
from universe_sim.systems import Univers
from universe_sim.values import Duree, GrandeurPhysique, Instant, Vecteur3


class BallisticClassicIntegrator:
    def avancer(self, universe, _engine, instant, dt):
        for body in universe.corps_physiques:
            translation = body.etat().translation
            if translation is not None:
                translation.position = translation.position + translation.vitesse * dt
                body.etat().instant = Instant(instant.seconds + dt)


class MultiRegimeTests(unittest.TestCase):
    def make_simulation(self):
        classic = CorpsPhysique(
            "planet",
            EtatPhysique(
                Instant(0.0),
                translation=EtatTranslationnel(Vecteur3.zero(), Vecteur3(1000.0, 0.0, 0.0)),
                massique=EtatMassique(GrandeurPhysique(1e20, "kg")),
            ),
        )
        sr = CorpsPhysique(
            "ship",
            EtatPhysique(
                Instant(0.0),
                massique=EtatMassique(GrandeurPhysique(1000.0, "kg")),
                relativiste=EtatCinematiqueRelativiste.depuis_vitesse(
                    Vecteur3.zero(), Vecteur3(0.8 * C, 0.0, 0.0), 1000.0
                ),
            ),
        )
        gamma = 1.0 / (1.0 - 0.25) ** 0.5
        gr = CorpsPhysique(
            "probe",
            EtatPhysique(
                Instant(0.0),
                espace_temps=EtatSpatioTemporelRelativiste(
                    (0.0, 0.0, 0.0, 0.0),
                    (gamma, 0.5 * gamma, 0.0, 0.0),
                    type_causal=TypeCourbeCausale.TEMPORELLE,
                    temps_propre_s=0.0,
                ),
            ),
        )
        universe = Univers("mixed", corps_physiques=[classic, sr, gr])
        configuration = ConfigurationPhysique()
        simulation = SimulationMultiRegime(
            universe,
            HorlogeSimulation(Instant(0.0), Duree(10.0)),
            configuration,
        )
        simulation.ajouter_evolution(
            EvolutionClassiqueGroupe((classic.id,), object(), BallisticClassicIntegrator())
        )
        simulation.ajouter_evolution(EvolutionSRCorps(sr.id))
        simulation.ajouter_evolution(
            EvolutionGeodesiqueCorps(gr.id, IntegrateurGeodesiqueRK4(MetriqueMinkowski()))
        )
        return simulation, classic, sr, gr

    def test_three_regimes_share_one_coordinate_clock(self):
        simulation, classic, sr, gr = self.make_simulation()
        simulation.avancer()
        self.assertEqual(simulation.horloge.instant_courant.seconds, 10.0)
        self.assertAlmostEqual(classic.etat().position().x, 10_000.0)
        self.assertLess(abs(sr.etat().position().x - 0.8 * C * 10.0) / C, 1e-12)
        self.assertLess(abs(gr.etat().position().x - 0.5 * C * 10.0) / C, 1e-12)
        self.assertTrue(all(body.etat().instant.seconds == 10.0 for body in (classic, sr, gr)))
        self.assertLess(sr.etat().relativiste.temps_propre_s, 10.0)
        self.assertLess(gr.etat().espace_temps.temps_propre_s, 10.0)

    def test_body_cannot_be_owned_by_two_regimes(self):
        simulation, _classic, sr, _gr = self.make_simulation()
        with self.assertRaises(ValueError):
            simulation.ajouter_evolution(EvolutionSRCorps(sr.id))

    def test_transaction_rolls_back_if_an_evolution_fails(self):
        simulation, classic, _sr, gr = self.make_simulation()
        original = simulation.evolutions[-1]

        class FailingEvolution:
            regime = original.regime

            @property
            def corps_ids(self):
                return original.corps_ids

            def avancer(self, universe, _instant, _dt):
                body = universe.trouver_corps(gr.id)
                body.etat().espace_temps.coordonnees_m = (999.0, 999.0, 0.0, 0.0)
                raise RuntimeError("boom")

        simulation.evolutions[-1] = FailingEvolution()
        before = classic.etat().position()
        with self.assertRaises(RuntimeError):
            simulation.avancer()
        self.assertEqual(classic.etat().position(), before)
        self.assertEqual(gr.etat().espace_temps.coordonnees_m[0], 0.0)
        self.assertEqual(simulation.horloge.instant_courant.seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
