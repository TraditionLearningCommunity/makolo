import json
import numpy as np

from universe_sim.persistence.large_scale import ConfigurationPersistanceGrandeEchelle, EcrivainEtatsChunkesNPZ
from universe_sim.simulation.array_backend import ArrayStateBackend


def _backend():
    return ArrayStateBackend(
        ("a", "b", "tracer"),
        np.zeros((3, 3)),
        np.array([[1., 0, 0], [0, 2., 0], [0, 0, 3.]]),
        np.array([[2., 0, 0], [0, 6., 0], [0, 0, 0.]]),
        np.array([2., 3., 0.]),
        np.zeros(3),
        np.array([np.nan, 7., np.nan]),
        np.ones(3, dtype=bool),
        np.array([0, 1, 0], dtype=np.int8),
    )


def test_chunked_writer_bounds_frames_and_preserves_canonical_state(tmp_path):
    backend = _backend()
    writer = EcrivainEtatsChunkesNPZ(ConfigurationPersistanceGrandeEchelle(tmp_path, frames_par_chunk=2))
    for i in range(5):
        backend.positions_m[:, 0] = i
        writer.ajouter_frame(i * 10, backend)
    writer.finaliser()
    chunks = sorted((tmp_path / "states" / "chunks").glob("*.npz"))
    assert len(chunks) == 3
    with np.load(chunks[0]) as data:
        assert data["positions_m"].shape == (2, 3, 3)
        assert data["momenta_kg_m_s"].shape == (2, 3, 3)
        assert data["tracer_velocities_m_s"].shape == (2, 1, 3)
        assert np.allclose(data["times_s"], [0, 10])
    with np.load(tmp_path / "catalogue" / "bodies.npz") as catalog:
        assert list(catalog["body_ids"]) == ["a", "b", "tracer"]
        assert np.array_equal(catalog["tracer_indices"], [2])
    index = json.loads((tmp_path / "states" / "index.json").read_text())
    assert [chunk["frames"] for chunk in index["chunks"]] == [2, 2, 1]
    assert index["body_count"] == 3


def test_registry_change_is_rejected(tmp_path):
    backend = _backend()
    writer = EcrivainEtatsChunkesNPZ(ConfigurationPersistanceGrandeEchelle(tmp_path))
    writer.ajouter_frame(0, backend)
    other = backend.copier()
    other.body_ids = ("x", "b", "tracer")
    other._index = {"x": 0, "b": 1, "tracer": 2}
    try:
        writer.ajouter_frame(1, other)
    except ValueError as exc:
        assert "registry changed" in str(exc)
    else:
        raise AssertionError("expected registry rejection")
