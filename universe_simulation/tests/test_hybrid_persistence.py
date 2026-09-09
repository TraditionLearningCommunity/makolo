import json
import numpy as np

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import C
from universe_sim.metrics import MetriqueMinkowski
from universe_sim.persistence.multidomain import (
    ConfigurationSessionGrandeEchelle,
    SessionPersistanceGrandeEchelleMultiDomaine,
)
from universe_sim.relativistic_state import EtatCinematiqueRelativiste
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.simulation.dynamic_migration import DomaineObjetsRelativistesGeneraux, GestionnaireMigrationRegime
from universe_sim.simulation.geodesic_integrator import IntegrateurGeodesiqueRK4
from universe_sim.simulation.large_scale_engine import DomainePopulationSR, SimulationGrandeEchelleMultiRegime
from universe_sim.simulation.multiregime import EvolutionGeodesiqueCorps
from universe_sim.states import EtatMassique, EtatPhysique
from universe_sim.systems import Univers
from universe_sim.values import GrandeurPhysique, Instant, Vecteur3


def test_hybrid_persistence_keeps_array_ownership_and_materialized_gr_worldline(tmp_path):
    mass = 1000.
    body = CorpsPhysique(
        "ship",
        EtatPhysique(
            Instant(0),
            massique=EtatMassique(GrandeurPhysique(mass, "kg")),
            relativiste=EtatCinematiqueRelativiste.depuis_vitesse(
                Vecteur3.zero(), Vecteur3(.4 * C, 0, 0), mass
            ),
        ),
        id="ship",
    )
    universe = Univers(corps_physiques=[body])
    sr = DomainePopulationSR("ships", ArrayStateBackend.depuis_corps([body]))
    gr = DomaineObjetsRelativistesGeneraux("gr-local", universe)
    simulation = SimulationGrandeEchelleMultiRegime(Instant(0), [sr, gr])
    session = SessionPersistanceGrandeEchelleMultiDomaine(
        ConfigurationSessionGrandeEchelle(tmp_path, frames_par_chunk=3)
    )
    session.ajouter_frame(simulation)

    metric = MetriqueMinkowski()
    manager = GestionnaireMigrationRegime()
    events = manager.materialiser_sr_vers_gr(
        universe,
        sr,
        gr,
        body.id,
        metric,
        EvolutionGeodesiqueCorps(body.id, IntegrateurGeodesiqueRK4(metric)),
        Instant(0),
    )
    session.ajouter_frame(simulation, events)
    simulation.avancer(1.)
    session.ajouter_frame(simulation)
    session.finaliser(simulation)

    chunk_path = tmp_path / "domains" / "ships" / "states" / "chunks" / "states_000000.npz"
    with np.load(chunk_path) as chunk:
        assert chunk["participating"][:, 0].tolist() == [True, False, False]
        assert chunk["active"][:, 0].tolist() == [True, True, True]

    worldline = tmp_path / "domains" / "gr-local" / "states" / "worldlines.jsonl"
    records = [json.loads(line) for line in worldline.read_text().splitlines() if line]
    assert len(records) == 2
    assert records[0]["instant_s"] == 0.0
    assert records[1]["instant_s"] == 1.0
    assert records[1]["body_id"] == body.id
    assert records[1]["proper_time_s"] > records[0]["proper_time_s"]

    metadata = json.loads((tmp_path / "metadata.json").read_text())
    storage = {domain["name"]: domain["storage"] for domain in metadata["domains"]}
    assert storage == {"gr-local": "gr-worldlines-jsonl", "ships": "chunked-npz"}
