import numpy as np

from universe_sim.constants import C
from universe_sim.examples.multigalaxy_gr_refinement import (
    etat_vaisseau_sr_dans_cadre_galaxie,
    materialiser_trou_noir_central,
    materialiser_vaisseau_local,
    metrique_trou_noir_central,
)
from universe_sim.examples.multigalaxy_scenario import construire_scenario_multi_galaxies
from universe_sim.metrics import MetriqueSchwarzschildKerrSchild
from universe_sim.values import Instant


def test_ship_transition_preserves_rest_mass_and_proper_time():
    scenario = construire_scenario_multi_galaxies("mini", 10.0)
    row = 0
    target = int(scenario.catalogue.cibles_galaxies_vaisseaux[row])
    initial_tau = float(scenario.vaisseaux.backend.proper_times_s[row])
    local = etat_vaisseau_sr_dans_cadre_galaxie(scenario, row, target, Instant(0.0))
    state = local.etat_sr_local
    assert state.relativiste is not None
    assert state.relativiste.temps_propre_s == initial_tau
    assert state.vitesse().norm() < C
    mass = state.massique.masse.value
    assert np.isclose(local.quadrimpulsion_locale.invariant_masse2(), mass * mass, rtol=1e-11)


def test_central_black_hole_materializes_with_consistent_schwarzschild_metric():
    scenario = construire_scenario_multi_galaxies("mini", 10.0)
    black_hole = materialiser_trou_noir_central(scenario.catalogue, 0)
    metric = metrique_trou_noir_central(scenario.catalogue, 0)
    assert isinstance(metric, MetriqueSchwarzschildKerrSchild)
    assert np.isclose(metric.rayon_schwarzschild_m, black_hole.rayon_reference.value)


def test_materialized_ship_keeps_hot_backend_identity():
    scenario = construire_scenario_multi_galaxies("mini", 10.0)
    target = int(scenario.catalogue.cibles_galaxies_vaisseaux[1])
    ship, local = materialiser_vaisseau_local(scenario, 1, target, Instant(0.0))
    assert ship.id == scenario.vaisseaux.backend.body_ids[1]
    assert ship.etat().relativiste is not None
    assert ship.etat().referentiel is local.etat_sr_local.referentiel
