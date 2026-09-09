import numpy as np

from universe_sim.bodies import CorpsPhysique
from universe_sim.constants import C
from universe_sim.events import TypeEvenementSimulation
from universe_sim.metrics import MetriqueMinkowski
from universe_sim.relativistic_state import EtatCinematiqueRelativiste
from universe_sim.simulation.array_backend import ArrayStateBackend
from universe_sim.simulation.dynamic_migration import (
    DomaineObjetsRelativistesGeneraux,
    GestionnaireMigrationRegime,
)
from universe_sim.simulation.geodesic_integrator import IntegrateurGeodesiqueRK4
from universe_sim.simulation.large_scale_engine import DomainePopulationSR, SimulationGrandeEchelleMultiRegime
from universe_sim.simulation.multiregime import EvolutionGeodesiqueCorps
from universe_sim.states import EtatMassique, EtatPhysique
from universe_sim.systems import Univers
from universe_sim.values import GrandeurPhysique, Instant, Vecteur3


def make_scene(beta=.5):
    mass = 1000.
    body = CorpsPhysique(
        "ship",
        EtatPhysique(
            Instant(0),
            massique=EtatMassique(GrandeurPhysique(mass, "kg")),
            relativiste=EtatCinematiqueRelativiste.depuis_vitesse(
                Vecteur3.zero(), Vecteur3(beta * C, 0, 0), mass
            ),
        ),
        id="ship-id",
    )
    universe = Univers(corps_physiques=[body])
    source = DomainePopulationSR("sr-pop", ArrayStateBackend.depuis_corps([body]))
    target = DomaineObjetsRelativistesGeneraux("gr-local", universe)
    metric = MetriqueMinkowski()
    evolution = EvolutionGeodesiqueCorps(body.id, IntegrateurGeodesiqueRK4(metric))
    return body, universe, source, target, metric, evolution


def test_sr_to_gr_migration_transfers_numerical_ownership_without_deactivating_body():
    body, universe, source, target, metric, evolution = make_scene()
    simulation = SimulationGrandeEchelleMultiRegime(Instant(0), [source, target])
    manager = GestionnaireMigrationRegime()
    events = manager.materialiser_sr_vers_gr(
        universe, source, target, body.id, metric, evolution, Instant(0)
    )
    assert body.actif
    assert not source.backend.participating[source.backend.index(body.id)]
    assert body.etat().espace_temps is not None
    assert simulation.proprietaires()[body.id] == target.nom
    assert {event.type for event in events} == {
        TypeEvenementSimulation.CHANGEMENT_REGIME_DYNAMIQUE,
        TypeEvenementSimulation.MATERIALISATION_LOD,
    }
    before = body.etat().position().x
    simulation.avancer(1.)
    assert body.etat().position().x > before
    assert source.backend.positions_m[source.backend.index(body.id), 0] == 0.0


def test_gr_to_sr_return_requires_explicit_sr_state_and_reactivates_hot_row():
    body, universe, source, target, metric, evolution = make_scene(beta=.3)
    simulation = SimulationGrandeEchelleMultiRegime(Instant(0), [source, target])
    manager = GestionnaireMigrationRegime()
    manager.materialiser_sr_vers_gr(universe, source, target, body.id, metric, evolution, Instant(0))
    simulation.avancer(2.)
    curved = body.etat()
    position = curved.position()
    velocity = curved.vitesse()
    proper_time = curved.espace_temps.temps_propre_s
    explicit_sr = EtatPhysique(
        Instant(2.),
        massique=EtatMassique(GrandeurPhysique(1000., "kg")),
        relativiste=EtatCinematiqueRelativiste.depuis_vitesse(
            position, velocity, 1000., proper_time
        ),
    )
    events = manager.dematerialiser_gr_vers_sr(
        universe, target, source, body.id, explicit_sr, Instant(2.)
    )
    assert body.etat().relativiste is not None
    assert body.etat().espace_temps is None
    assert source.backend.participating[source.backend.index(body.id)]
    assert body.id not in target.evolutions
    assert simulation.proprietaires()[body.id] == source.nom
    assert {event.type for event in events} == {
        TypeEvenementSimulation.CHANGEMENT_REGIME_DYNAMIQUE,
        TypeEvenementSimulation.DEMATERIALISATION_LOD,
    }
    before = source.backend.positions_m[source.backend.index(body.id), 0]
    simulation.avancer(1.)
    assert source.backend.positions_m[source.backend.index(body.id), 0] > before


def test_multiple_simultaneous_owners_are_rejected():
    body, universe, source, target, metric, evolution = make_scene()
    target.ajouter_evolution(evolution)
    try:
        SimulationGrandeEchelleMultiRegime(Instant(0), [source, target])
    except RuntimeError as exc:
        assert "multiple" in str(exc).lower() or "simultaneously" in str(exc).lower()
    else:
        raise AssertionError("expected duplicate numerical ownership rejection")
