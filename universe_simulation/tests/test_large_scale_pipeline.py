import json
import numpy as np

from universe_sim.constants import C
from universe_sim.gravity import SolveurGraviteDirect
from universe_sim.persistence.multidomain import (
    ConfigurationSessionGrandeEchelle,
    SessionPersistanceGrandeEchelleMultiDomaine,
)
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.simulation.large_scale_engine import (
    DomainePopulationClassique,
    DomainePopulationSR,
    SimulationGrandeEchelleMultiRegime,
)
from universe_sim.simulation.population import IntegrateurPopulationNewtonienneTableau
from universe_sim.values import Instant


def test_mixed_newton_sr_pipeline_persists_authoritative_hot_state(tmp_path):
    rng = np.random.default_rng(91)
    n_stars = 64
    star_positions = rng.uniform(-1e13, 1e13, size=(n_stars, 3))
    star_velocities = rng.normal(0, 1000, size=(n_stars, 3))
    star_masses = 10 ** rng.uniform(26, 30, size=n_stars)
    stars = ArrayStateBackend(
        tuple(f"star-{i}" for i in range(n_stars)),
        star_positions,
        star_velocities,
        star_velocities * star_masses[:, None],
        star_masses,
        np.zeros(n_stars),
        np.full(n_stars, np.nan),
        np.ones(n_stars, dtype=bool),
        np.zeros(n_stars, dtype=np.int8),
    )

    n_ships = 256
    ship_masses = 10 ** rng.uniform(3, 7, size=n_ships)
    directions = rng.normal(size=(n_ships, 3))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    beta = rng.uniform(.2, .995, size=n_ships)
    gamma = 1 / np.sqrt(1 - beta * beta)
    ship_velocities = directions * (beta * C)[:, None]
    ship_momenta = directions * (gamma * ship_masses * beta * C)[:, None]
    ships = ArrayStateBackend(
        tuple(f"ship-{i}" for i in range(n_ships)),
        rng.uniform(-1e11, 1e11, size=(n_ships, 3)),
        ship_velocities,
        ship_momenta,
        ship_masses,
        np.zeros(n_ships),
        np.zeros(n_ships),
        np.ones(n_ships, dtype=bool),
        np.ones(n_ships, dtype=np.int8),
    )

    def thrust(backend, instant):
        force = np.zeros_like(backend.momenta_kg_m_s)
        sign = 1.0 if instant.seconds < 100.0 else -1.0
        force[:, 0] = sign * 2e8
        return force

    classical_domain = DomainePopulationClassique(
        "stellar-population",
        stars,
        IntegrateurPopulationNewtonienneTableau(
            SolveurGraviteDirect(block_size=32, softening_m=1e6)
        ),
    )
    sr_domain = DomainePopulationSR("relativistic-ships", ships, force_provider=thrust)
    simulation = SimulationGrandeEchelleMultiRegime(Instant(0), [classical_domain, sr_domain])
    persistence = SessionPersistanceGrandeEchelleMultiDomaine(
        ConfigurationSessionGrandeEchelle(tmp_path, frames_par_chunk=3)
    )
    persistence.ajouter_frame(simulation)
    for step in range(20):
        events = simulation.avancer(10.0)
        if (step + 1) % 5 == 0:
            persistence.ajouter_frame(simulation, events)
    persistence.finaliser(simulation)

    assert simulation.instant_courant.seconds == 200.0
    assert simulation.pas_effectues == 20
    assert np.all(np.linalg.norm(ships.velocities_m_s, axis=1) < C)
    assert np.all(ships.proper_times_s > 0)
    assert np.all(ships.proper_times_s < 200.0)
    assert np.all(np.isfinite(stars.positions_m))
    assert np.all(np.isfinite(ships.positions_m))

    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["frames"] == 5
    assert metadata["steps"] == 20
    assert {domain["regime"] for domain in metadata["domains"]} == {
        "classique",
        "relativiste_special",
    }
