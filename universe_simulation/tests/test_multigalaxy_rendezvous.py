import numpy as np

from universe_sim.constants import C
from universe_sim.examples.multigalaxy_rendezvous import planifier_rendezvous_mobiles
from universe_sim.examples.multigalaxy_scenario import construire_scenario_multi_galaxies


def test_mobile_rendezvous_retargets_reachable_ship_and_synchronizes_galaxy_cadence():
    scenario = construire_scenario_multi_galaxies(
        "mini",
        5_000_000.0,
        pas_vaisseaux_annees=5_000.0,
        pas_galaxies_annees=10_000.0,
    )
    catalogue = scenario.catalogue
    inter = np.flatnonzero(catalogue.cibles_systemes_vaisseaux < 0)
    start = scenario.vaisseaux.backend.positions_m
    target = catalogue.positions_galaxies_m[catalogue.cibles_galaxies_vaisseaux]
    distance = np.linalg.norm(target - start, axis=1)
    estimated_time = distance / np.maximum(catalogue.beta_vaisseaux * C, 1.0)
    row = int(inter[np.argmin(estimated_time[inter])])
    dives = np.zeros(len(start), dtype=np.bool_)
    dives[row] = True

    speed_before = np.linalg.norm(scenario.vaisseaux.backend.velocities_m_s[row])
    plan = planifier_rendezvous_mobiles(scenario, plongees_bh=dives)

    assert plan.temps_arrivee_s.shape == (len(start),)
    assert plan.cibles_predites_m.shape == start.shape
    assert plan.atteignable[row]
    assert plan.plongee_bh[row]
    assert 0.0 < plan.temps_arrivee_s[row] <= scenario.duree_s
    assert scenario.simulation.cadences[scenario.galaxies.nom].pas_s == scenario.simulation.cadences[scenario.vaisseaux.nom].pas_s

    velocity = scenario.vaisseaux.backend.velocities_m_s[row]
    direction = plan.cibles_predites_m[row] - start[row]
    direction /= np.linalg.norm(direction)
    assert np.dot(velocity / np.linalg.norm(velocity), direction) > 1.0 - 1e-10
    assert np.isclose(np.linalg.norm(velocity), speed_before, rtol=1e-12)
    assert scenario.vaisseaux.force_provider is scenario.propulsion
