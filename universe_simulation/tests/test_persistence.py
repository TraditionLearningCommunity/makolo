import csv
import json
import tempfile
import unittest
from pathlib import Path

from universe_sim.examples import construire_systeme_solaire_minimal
from universe_sim.persistence import ConfigurationPersistance, SessionPersistance
from universe_sim.spacetime import ORIGINE_SIMULATION, REFERENTIEL_SIMULATION
from universe_sim.values import Instant


class PersistenceTests(unittest.TestCase):
    def test_time_and_space_zero_are_reference_values(self):
        self.assertLess(Instant(-1.0).seconds, 0.0)
        self.assertIn("simulation", ORIGINE_SIMULATION.nom.lower())
        self.assertIn("simulation", REFERENTIEL_SIMULATION.nom.lower())

    def test_run_is_persisted_as_csv_and_metadata(self):
        simulation = construire_systeme_solaire_minimal(dt=3600.0)
        initial = simulation.diagnostic()
        with tempfile.TemporaryDirectory() as temp:
            session = SessionPersistance.demarrer(
                simulation,
                ConfigurationPersistance(save_simulation=True, dossier_racine=temp, nom_execution="test-run"),
                scene="minimal",
                diagnostic_initial=initial,
            )
            simulation.avancer()
            folder = session.finaliser(simulation)
            self.assertTrue((folder / "metadata.json").exists())
            self.assertTrue((folder / "manifest.json").exists())
            self.assertTrue((folder / "data" / "bodies.csv").exists())
            self.assertTrue((folder / "data" / "states.csv").exists())
            self.assertTrue((folder / "data" / "diagnostics.csv").exists())
            self.assertTrue((folder / "images").is_dir())
            self.assertTrue((folder / "videos").is_dir())
            self.assertTrue((folder / "interactive").is_dir())

            metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
            self.assertIn("not the beginning", metadata["semantics"]["time_zero"])
            self.assertIn("not an absolute center", metadata["semantics"]["space_origin"])

            with (folder / "data" / "states.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertGreater(len(rows), 0)
