import numpy as np

from universe_sim.examples.multigalaxy_scenario import construire_scenario_multi_galaxies


def test_mini_multirate_scenario_reaches_common_barrier_and_stays_causal():
    scenario = construire_scenario_multi_galaxies(
        "mini",
        200.0,
        pas_vaisseaux_annees=1.0,
        pas_galaxies_annees=20.0,
    )
    result = scenario.executer()
    assert result["coordinate_time_years"] == 200.0
    assert result["catalogue_entities"] == 5_000
    assert result["sr_vehicles"] == 120
    assert 0.0 <= result["beta_min"] < 1.0
    assert result["beta_max"] < 1.0
    assert 0.0 < result["proper_time_min_years"] <= 200.0
    assert result["proper_time_max_years"] <= 200.0
    assert scenario.simulation.simultanes()


def test_propulsion_program_has_coast_acceleration_and_braking_modes():
    scenario = construire_scenario_multi_galaxies("10k", 1_000.0)
    modes = scenario.catalogue.modes_mission_vaisseaux
    assert set(np.unique(modes)) == {0, 1, 2, 3}
    initial = scenario.propulsion(scenario.vaisseaux.backend, scenario.simulation.origine_temps)
    coast = modes == 0
    assert np.allclose(initial[coast], 0.0)
    assert np.any(np.linalg.norm(initial[modes == 1], axis=1) > 0.0)


def test_summary_reports_intended_intergalactic_missions():
    scenario = construire_scenario_multi_galaxies("mini", 10.0)
    result = scenario.resume()
    assert result["intergalactic_missions"] > 0
    assert result["beta_max"] < 1.0
