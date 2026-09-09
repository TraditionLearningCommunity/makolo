import numpy as np

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import C, G, SOLAR_MASS
from universe_sim.gravity.environment import (
    SourcesPotentielAgregees,
    diagnostiquer_population_sr,
    evaluer_potentiel_lointain,
)
from universe_sim.regimes import NiveauActiviteCalcul, RegimeDynamique
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.simulation.hierarchy import EtatAgregeSysteme, RegistreHierarchiqueUnivers
from universe_sim.states import EtatMassique, EtatPhysique, EtatTranslationnel
from universe_sim.systems import SystemePhysique, Univers
from universe_sim.values import GrandeurPhysique, Instant, Vecteur3


def aggregate(system_id="sys", mass=SOLAR_MASS, radius=0.0):
    return EtatAgregeSysteme(
        system_id,
        mass,
        Vecteur3.zero(),
        Vecteur3.zero(),
        radius,
        ((0., 0., 0.), (0., 0., 0.), (0., 0., 0.)),
        (),
        NiveauActiviteCalcul.AGGREGATED,
    )


def test_far_potential_matches_single_monopole_and_flags_coverage():
    source = SourcesPotentielAgregees.depuis_agregats((aggregate(radius=1e6),))
    targets = np.array([[1e9, 0., 0.], [5e5, 0., 0.]])
    result = evaluer_potentiel_lointain(targets, source)
    assert np.isclose(result.potentiel_j_kg[0], -G * SOLAR_MASS / 1e9, rtol=1e-14)
    assert not result.dans_couverture_source[0]
    assert result.dans_couverture_source[1]
    assert result.source_proche_index.tolist() == [0, 0]


def test_sr_regime_diagnostic_uses_potential_without_applying_newtonian_force():
    gravitational_length = G * SOLAR_MASS / (C * C)
    positions = np.array([[1e18, 0., 0.], [20 * gravitational_length, 0., 0.]])
    masses = np.array([1000., 1000.])
    beta = .8
    gamma = 1 / np.sqrt(1 - beta * beta)
    velocities = np.array([[beta * C, 0., 0.], [beta * C, 0., 0.]])
    momenta = velocities * (gamma * masses)[:, None]
    backend = ArrayStateBackend(
        ("far", "near"), positions, velocities, momenta, masses,
        np.zeros(2), np.zeros(2), np.ones(2, dtype=bool), np.ones(2, dtype=np.int8),
    )
    source = SourcesPotentielAgregees.depuis_agregats((aggregate(),))
    result = diagnostiquer_population_sr(backend, source)
    assert result.diagnostics[0].regime == RegimeDynamique.RELATIVISTE_SPECIAL
    assert result.diagnostics[1].regime == RegimeDynamique.RELATIVISTE_GENERAL
    # Diagnostic query must not mutate trajectory/momentum.
    assert np.array_equal(backend.positions_m, positions)
    assert np.array_equal(backend.momenta_kg_m_s, momenta)


def test_hierarchy_frontier_never_double_counts_aggregated_parent_and_child():
    body = CorpsPhysique(
        "star",
        EtatPhysique(
            Instant(0),
            translation=EtatTranslationnel(Vecteur3.zero(), Vecteur3.zero()),
            massique=EtatMassique(GrandeurPhysique(SOLAR_MASS, "kg")),
        ),
        id="star",
    )
    child = SystemePhysique("child", membres=[body], id="child")
    parent = SystemePhysique("parent", sous_systemes=[child], id="parent")
    universe = Univers(corps_physiques=[body], systemes_physiques=[parent, child])
    registry = RegistreHierarchiqueUnivers(universe)
    assert [state.systeme_id for state in registry.frontiere_agregee()] == ["parent"]
    registry.definir_niveau("parent", NiveauActiviteCalcul.ACTIVE)
    assert [state.systeme_id for state in registry.frontiere_agregee()] == ["child"]
