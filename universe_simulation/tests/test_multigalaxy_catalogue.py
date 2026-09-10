import numpy as np

from universe_sim.constants import C
from universe_sim.examples.multigalaxy_catalogue import (
    CONFIGURATIONS_MULTI_GALAXIES,
    TypeCadreCatalogue,
    TypeEntiteCatalogue,
    compteurs_configuration,
    generer_catalogue_multi_galaxies,
)


def test_500k_preset_has_exact_requested_population():
    counts = compteurs_configuration(CONFIGURATIONS_MULTI_GALAXIES["500k"])
    assert sum(counts.values()) == 500_000
    assert counts == {
        "black_holes": 10,
        "stars": 2_760,
        "planets": 19_200,
        "moons": 48_000,
        "asteroids": 383_030,
        "comets": 12_000,
        "debris": 30_000,
        "ships": 5_000,
    }


def test_mini_catalogue_is_deterministic_hierarchical_and_finite():
    first = generer_catalogue_multi_galaxies("mini")
    second = generer_catalogue_multi_galaxies("mini")
    assert first.nombre_entites == 5_000
    assert first.compteurs() == second.compteurs()
    assert np.array_equal(first.galaxie_par_systeme, second.galaxie_par_systeme)
    assert np.allclose(first.positions_galaxies_m, second.positions_galaxies_m)
    assert np.allclose(first.positions_locales_m, second.positions_locales_m)
    assert np.all(np.isfinite(first.positions_locales_m))
    assert np.all(np.isfinite(first.vitesses_locales_m_s))
    ships = first.tranches["ships"]
    black_holes = first.tranches["black_holes"]
    assert np.all(first.types_cadres[ships] == int(TypeCadreCatalogue.GROUPE_GALACTIQUE))
    assert np.all(first.types_cadres[black_holes] == int(TypeCadreCatalogue.GALAXIE))
    assert np.all(first.types_entites[ships] == int(TypeEntiteCatalogue.VEHICULE_SR))
    assert np.all(np.linalg.norm(first.vitesses_locales_m_s[ships], axis=1) < C)


def test_compact_backends_expose_only_hot_populations():
    catalogue = generer_catalogue_multi_galaxies("10k")
    galaxies = catalogue.backend_galaxies()
    ships = catalogue.backend_vaisseaux_sr()
    assert len(galaxies.body_ids) == 5
    assert len(ships.body_ids) == 300
    assert np.all(galaxies.regime_codes == 0)
    assert np.all(ships.regime_codes == 1)
    assert np.all(ships.masque_evolution())
    assert np.all(np.linalg.norm(ships.velocities_m_s, axis=1) < C)


def test_inertial_registry_has_group_galaxy_and_system_frames():
    catalogue = generer_catalogue_multi_galaxies("mini")
    registry = catalogue.construire_registre_cadres()
    assert registry.racine.id == "frame-group"
    assert len(registry.cadres) == 1 + 3 + 45
    for system_index in range(45):
        frame = registry.obtenir(catalogue.id_cadre_systeme(system_index))
        galaxy_index = int(catalogue.galaxie_par_systeme[system_index])
        assert frame.parent_id == catalogue.id_cadre_galaxie(galaxy_index)


def test_materialization_opens_one_system_without_materializing_catalogue():
    catalogue = generer_catalogue_multi_galaxies("mini")
    system_index = 7
    expected = catalogue.indices_entites_systeme(system_index)
    system = catalogue.materialiser_systeme(system_index)
    assert system.id == catalogue.id_systeme(system_index)
    assert len(system.membres) == len(expected)
    assert system.valider()
    assert all(body.etat().referentiel is system.membres[0].etat().referentiel for body in system.membres)
