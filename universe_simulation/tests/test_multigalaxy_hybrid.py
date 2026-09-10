import numpy as np

from universe_sim.constants import C, G
from universe_sim.examples.multigalaxy_hybrid import (
    _fractions_entree_spheres,
    construire_execution_hybride_multi_galaxies,
    diversifier_cibles_intergalactiques,
)
from universe_sim.examples.multigalaxy_scenario import construire_scenario_multi_galaxies


def test_target_diversification_keeps_only_small_deterministic_bh_dive_set():
    scenario = construire_scenario_multi_galaxies("mini", 1000.0)
    dive = diversifier_cibles_intergalactiques(scenario, nombre_plongees_bh=3)
    assert np.count_nonzero(dive) <= 3
    assert np.all(np.linalg.norm(scenario.vaisseaux.backend.velocities_m_s, axis=1) < C)


def test_vectorized_sphere_entry_finds_continuous_crossing():
    start = np.array([[2.0, 0, 0], [2.0, 0, 0], [.5, 0, 0]])
    end = np.array([[-2.0, 0, 0], [3.0, 0, 0], [.4, 0, 0]])
    r = np.ones(3)
    f = _fractions_entree_spheres(start, end, r, np.ones(3, dtype=bool))
    assert np.isclose(f[0], .25)
    assert np.isnan(f[1])
    assert f[2] == 0.0


def test_hybrid_execution_starts_with_unique_sr_ownership():
    scenario = construire_scenario_multi_galaxies("mini", 100.0)
    hybrid = construire_execution_hybride_multi_galaxies(scenario, nombre_plongees_bh=2)
    assert len(hybrid.domaine_gr.corps_participants) == 0
    assert len(hybrid.scenario.vaisseaux.corps_participants) == 120
    target = scenario.catalogue.cibles_galaxies_vaisseaux
    bh = scenario.catalogue.tranches["black_holes"]
    mass = scenario.catalogue.masses_kg[bh][target]
    transition = hybrid._rayons_transition()
    assert np.allclose(G * mass / (transition * C * C), hybrid.precision_transition_gr)
