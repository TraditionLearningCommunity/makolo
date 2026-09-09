import json
import numpy as np
from types import SimpleNamespace

from universe_sim.persistence.multidomain import (
    ConfigurationSessionGrandeEchelle,
    SessionPersistanceGrandeEchelleMultiDomaine,
)
from universe_sim.regimes import RegimeDynamique
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.values import Instant


def backend(ids, code):
    n = len(ids)
    masses = np.arange(1, n + 1, dtype=float)
    return ArrayStateBackend(
        tuple(ids), np.zeros((n, 3)), np.zeros((n, 3)), np.zeros((n, 3)), masses,
        np.zeros(n), np.zeros(n) if code else np.full(n, np.nan), np.ones(n, dtype=bool),
        np.full(n, code, dtype=np.int8),
    )


def test_multiple_hot_domains_are_persisted_without_object_sync(tmp_path):
    classical = SimpleNamespace(
        nom="stars", regime=RegimeDynamique.CLASSIQUE, backend=backend(["s1", "s2"], 0)
    )
    relativistic = SimpleNamespace(
        nom="fast ships", regime=RegimeDynamique.RELATIVISTE_SPECIAL,
        backend=backend(["v1", "v2", "v3"], 1),
    )
    simulation = SimpleNamespace(
        domaines=[classical, relativistic], instant_courant=Instant(0), pas_effectues=0
    )
    session = SessionPersistanceGrandeEchelleMultiDomaine(
        ConfigurationSessionGrandeEchelle(tmp_path, frames_par_chunk=2)
    )
    session.ajouter_frame(simulation)
    classical.backend.positions_m[:, 0] += 1
    relativistic.backend.positions_m[:, 0] += 2
    simulation.instant_courant = Instant(10)
    simulation.pas_effectues = 1
    session.ajouter_frame(simulation)
    session.finaliser(simulation)
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["frames"] == 2 and metadata["steps"] == 1
    assert {d["name"] for d in metadata["domains"]} == {"stars", "fast ships"}
    assert (tmp_path / "domains" / "stars" / "states" / "chunks" / "states_000000.npz").exists()
    assert (tmp_path / "domains" / "fast-ships" / "states" / "chunks" / "states_000000.npz").exists()


def test_domain_registry_change_is_rejected(tmp_path):
    classical = SimpleNamespace(
        nom="stars", regime=RegimeDynamique.CLASSIQUE, backend=backend(["s1"], 0)
    )
    simulation = SimpleNamespace(domaines=[classical], instant_courant=Instant(0), pas_effectues=0)
    session = SessionPersistanceGrandeEchelleMultiDomaine(ConfigurationSessionGrandeEchelle(tmp_path))
    session.ajouter_frame(simulation)
    simulation.domaines = []
    try:
        session.ajouter_frame(simulation)
    except ValueError as exc:
        assert "registry changed" in str(exc)
    else:
        raise AssertionError("expected domain registry rejection")
