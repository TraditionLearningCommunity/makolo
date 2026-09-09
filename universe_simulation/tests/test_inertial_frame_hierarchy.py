from universe_sim.constants import C
from universe_sim.relativistic_values import quadrimpulsion_depuis_vitesse
from universe_sim.services.inertial_frames import CadreInertielRelatif, RegistreCadresInertiels
from universe_sim.services.relativistic_geometry import EvenementMinkowski
from universe_sim.values import Vecteur3


def test_event_roundtrip_with_translation_and_relativistic_boost():
    root = CadreInertielRelatif("root", id="root")
    child = CadreInertielRelatif(
        "galaxy",
        parent_id="root",
        origine_dans_parent=EvenementMinkowski(100., Vecteur3(1e20, -2e20, 3e20)),
        vitesse_dans_parent=Vecteur3(.6 * C, 0, 0),
        id="galaxy",
    )
    registry = RegistreCadresInertiels(root)
    registry.ajouter(child)
    local = EvenementMinkowski(10., Vecteur3(2e9, 3e9, -4e9))
    parent = registry.transformer_evenement(local, "galaxy", "root")
    recovered = registry.transformer_evenement(parent, "root", "galaxy")
    assert abs(recovered.t_s - local.t_s) < 1e-12
    assert (recovered.position_m - local.position_m).norm() < 1e5  # ulp at 1e20-scale translation


def test_four_momentum_roundtrip_preserves_invariant_mass():
    root = CadreInertielRelatif("root", id="root")
    child = CadreInertielRelatif(
        "moving", parent_id="root", vitesse_dans_parent=Vecteur3(.7 * C, 0, 0), id="moving"
    )
    registry = RegistreCadresInertiels(root)
    registry.ajouter(child)
    p = quadrimpulsion_depuis_vitesse(1200., Vecteur3(.4 * C, .1 * C, 0))
    transformed = registry.transformer_quadrimpulsion(p, "moving", "root")
    recovered = registry.transformer_quadrimpulsion(transformed, "root", "moving")
    assert abs(transformed.invariant_masse2() - 1200.0 ** 2) / 1200.0 ** 2 < 1e-12
    assert abs(recovered.invariant_masse2() - p.invariant_masse2()) / p.invariant_masse2() < 1e-12
    assert (recovered.impulsion - p.impulsion).norm() / max(1., p.impulsion.norm()) < 1e-12


def test_nested_frames_roundtrip_without_flattening_large_and_local_coordinates():
    root = CadreInertielRelatif("group", id="group")
    galaxy = CadreInertielRelatif(
        "galaxy", parent_id="group",
        origine_dans_parent=EvenementMinkowski(0., Vecteur3(5e21, 0, 0)),
        vitesse_dans_parent=Vecteur3(1e5, 2e5, 0), id="galaxy",
    )
    system = CadreInertielRelatif(
        "system", parent_id="galaxy",
        origine_dans_parent=EvenementMinkowski(1000., Vecteur3(3e16, -2e16, 0)),
        vitesse_dans_parent=Vecteur3(3e4, 0, 0), id="system",
    )
    registry = RegistreCadresInertiels(root)
    registry.ajouter(galaxy)
    registry.ajouter(system)
    local = EvenementMinkowski(50., Vecteur3(1.5e11, 4e8, 0))
    global_event = registry.evenement_vers_racine(local, "system")
    recovered = registry.evenement_depuis_racine(global_event, "system")
    assert abs(recovered.t_s - local.t_s) < 1e-7
    assert (recovered.position_m - local.position_m).norm() < 2e6
    # The local state itself remains of AU scale rather than being stored near 5e21 m.
    assert local.position_m.norm() < 1e12
    assert global_event.position_m.norm() > 1e21
