import numpy as np

from universe_sim.examples.multigalaxy_analysis import analyser_navigation_multi_galaxies
from universe_sim.examples.multigalaxy_scenario import construire_scenario_multi_galaxies


def test_navigation_analysis_returns_one_result_per_vehicle():
    scenario = construire_scenario_multi_galaxies("mini", 500.0, pas_vaisseaux_annees=5.0, pas_galaxies_annees=50.0)
    scenario.executer()
    analysis = analyser_navigation_multi_galaxies(scenario)
    n = len(scenario.vaisseaux.backend.body_ids)
    assert analysis.distance_min_galaxie_m.shape == (n,)
    assert analysis.distance_min_systeme_m.shape == (n,)
    assert analysis.candidat_gr.shape == (n,)
    assert np.all(analysis.distance_min_bh_en_rs >= 0.0)


def test_gr_transition_radius_matches_reduced_potential_threshold():
    scenario = construire_scenario_multi_galaxies("mini", 10.0)
    analysis = analyser_navigation_multi_galaxies(scenario, precision_gr=1e-6)
    assert np.all(analysis.rayon_transition_gr_m > 0.0)
    target = scenario.catalogue.cibles_galaxies_vaisseaux
    bh = scenario.catalogue.tranches["black_holes"]
    mass = scenario.catalogue.masses_kg[bh][target]
    from universe_sim.constants import C, G
    reduced = G * mass / (analysis.rayon_transition_gr_m * C * C)
    assert np.allclose(reduced, 1e-6)
