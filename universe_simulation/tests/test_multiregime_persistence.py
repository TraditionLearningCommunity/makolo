import csv
import json
import tempfile
import unittest
from pathlib import Path

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import C
from universe_sim.metrics import MetriqueMinkowski
from universe_sim.persistence import ConfigurationPersistance, SessionPersistanceMultiRegime
from universe_sim.relativistic_state import EtatCinematiqueRelativiste, EtatSpatioTemporelRelativiste, TypeCourbeCausale
from universe_sim.simulation import (
    EvolutionGeodesiqueCorps,
    EvolutionSRCorps,
    HorlogeSimulation,
    IntegrateurGeodesiqueRK4,
    SimulationMultiRegime,
)
from universe_sim.simulation.configuration import ConfigurationPhysique
from universe_sim.states import EtatMassique, EtatPhysique
from universe_sim.systems import Univers
from universe_sim.values import Duree, GrandeurPhysique, Instant, Vecteur3


class MultiRegimePersistenceTests(unittest.TestCase):
    def test_sr_and_curved_states_are_persisted_without_newtonian_reduction(self):
        ship = CorpsPhysique(
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
        probe = CorpsPhysique(
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
        sim = SimulationMultiRegime(
            Univers("mixed", corps_physiques=[ship, probe]),
            HorlogeSimulation(Instant(0.0), Duree(1.0)),
            ConfigurationPhysique(conserver_historique=True),
        )
        sim.ajouter_evolution(EvolutionSRCorps(ship.id))
        sim.ajouter_evolution(EvolutionGeodesiqueCorps(probe.id, IntegrateurGeodesiqueRK4(MetriqueMinkowski())))

        with tempfile.TemporaryDirectory() as tmp:
            persistence = SessionPersistanceMultiRegime.demarrer(
                sim,
                ConfigurationPersistance(save_simulation=True, dossier_racine=tmp, nom_execution="mixed"),
                scene="mixed",
            )
            sim.avancer()
            folder = persistence.finaliser(sim)

            with (Path(folder) / "data" / "states.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            modes = {row["body_name"]: row["kinematic_mode"] for row in rows if float(row["instant_s"]) == 1.0}
            self.assertEqual(modes["ship"], "special_relativity")
            self.assertEqual(modes["probe"], "curved_spacetime")
            ship_row = next(row for row in rows if row["body_name"] == "ship" and float(row["instant_s"]) == 1.0)
            probe_row = next(row for row in rows if row["body_name"] == "probe" and float(row["instant_s"]) == 1.0)
            self.assertNotEqual(ship_row["momentum_x_kg_m_s"], "")
            self.assertNotEqual(ship_row["gamma_sr"], "")
            self.assertNotEqual(ship_row["proper_time_s"], "")
            self.assertNotEqual(probe_row["spacetime_ct_m"], "")
            self.assertNotEqual(probe_row["tangent_0"], "")
            self.assertNotEqual(probe_row["proper_time_s"], "")

            with (Path(folder) / "metadata.json").open(encoding="utf-8") as handle:
                metadata = json.load(handle)
            self.assertEqual(metadata["simulation"]["integrator"], "multi-regime")
            self.assertEqual(len(metadata["simulation"]["evolutions"]), 2)
            self.assertIsNone(metadata["final_diagnostic"]["mechanical_energy_j"])
            self.assertGreater(metadata["final_diagnostic"]["gamma_max_sr"], 1.0)


if __name__ == "__main__":
    unittest.main()
