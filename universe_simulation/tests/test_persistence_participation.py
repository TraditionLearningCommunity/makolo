import json
import numpy as np

from universe_sim.persistence.large_scale import (
    ConfigurationPersistanceGrandeEchelle,
    EcrivainEtatsChunkesNPZ,
)
from universe_sim.simulation.array_backend import ArrayStateBackend


def test_large_scale_persistence_distinguishes_physical_activity_and_backend_participation(tmp_path):
    backend = ArrayStateBackend(
        ("body",),
        np.zeros((1, 3)), np.zeros((1, 3)), np.zeros((1, 3)),
        np.array([1.]), np.zeros(1), np.full(1, np.nan),
        np.ones(1, dtype=bool), np.zeros(1, dtype=np.int8),
    )
    backend.suspendre_calcul("body")
    writer = EcrivainEtatsChunkesNPZ(
        ConfigurationPersistanceGrandeEchelle(tmp_path, frames_par_chunk=1)
    )
    writer.ajouter_frame(0.0, backend)
    writer.finaliser()

    with np.load(tmp_path / "catalogue" / "bodies.npz") as catalogue:
        assert bool(catalogue["active_initial"][0]) is True
        assert bool(catalogue["participating_initial"][0]) is False
    with np.load(tmp_path / "states" / "chunks" / "states_000000.npz") as chunk:
        assert bool(chunk["active"][0, 0]) is True
        assert bool(chunk["participating"][0, 0]) is False
    schema = json.loads((tmp_path / "states" / "index.json").read_text())
    assert schema["physical_activity"] == "active"
    assert schema["numerical_ownership"] == "participating"
