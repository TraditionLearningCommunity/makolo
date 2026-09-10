"""Local black-hole materialization helpers for multi-galaxy GR refinement."""
from __future__ import annotations

from dataclasses import dataclass

from ..bodies import TrouNoir, Vehicule
from ..constants import C, G
from ..relativistic_state import EtatCinematiqueRelativiste
from ..relativistic_values import Quadrimpulsion, energie_totale_relativiste
from ..services.inertial_frames import CadreInertielRelatif, RegistreCadresInertiels
from ..services.relativistic_geometry import EvenementMinkowski
from ..services.relativity import metrique_pour_trou_noir
from ..spacetime import ClassificationReferentiel, PointReference, Referentiel
from ..states import EtatMassique, EtatPhysique, EtatTranslationnel
from ..values import GrandeurPhysique, Instant, Vecteur3
from .multigalaxy_catalogue import CatalogueMultiGalaxies
from .multigalaxy_scenario import ScenarioMultiGalaxies


@dataclass(frozen=True, slots=True)
class EtatLocalTransitionGR:
    etat_sr_local: EtatPhysique
    temps_coordonne_local_s: float
    galaxie_index: int
    evenement_local: EvenementMinkowski
    quadrimpulsion_locale: Quadrimpulsion


def referentiel_local_trou_noir(galaxie_index: int) -> Referentiel:
    return Referentiel(
        f"Referentiel inertiel local trou noir galaxie {galaxie_index + 1}",
        PointReference(f"Centre trou noir galaxie {galaxie_index + 1}"),
        classification=ClassificationReferentiel.APPROXIMATIVEMENT_INERTIEL,
    )


def etat_vaisseau_sr_dans_cadre_galaxie(
    scenario: ScenarioMultiGalaxies,
    index_vaisseau: int,
    galaxie_index: int,
    instant: Instant,
    *,
    position_groupe_m: Vecteur3 | None = None,
    impulsion_groupe_kg_m_s: Vecteur3 | None = None,
    temps_propre_s: float | None = None,
    position_galaxie_m: Vecteur3 | None = None,
    vitesse_galaxie_m_s: Vecteur3 | None = None,
    referentiel_local: Referentiel | None = None,
) -> EtatLocalTransitionGR:
    catalogue = scenario.catalogue
    backend = scenario.vaisseaux.backend
    if not 0 <= index_vaisseau < len(backend.body_ids):
        raise IndexError(index_vaisseau)
    if not 0 <= galaxie_index < catalogue.configuration.nombre_galaxies:
        raise IndexError(galaxie_index)
    row = index_vaisseau
    mass = float(backend.masses_kg[row])
    if mass <= 0:
        raise ValueError("GR transition requires positive rest mass")

    position_group = position_groupe_m or Vecteur3.from_iterable(backend.positions_m[row])
    momentum_group = impulsion_groupe_kg_m_s or Vecteur3.from_iterable(backend.momenta_kg_m_s[row])
    proper_time = float(backend.proper_times_s[row]) if temps_propre_s is None else float(temps_propre_s)
    if proper_time < 0:
        raise ValueError("Accumulated proper time cannot be negative")
    galaxy_position = position_galaxie_m or Vecteur3.from_iterable(scenario.galaxies.backend.positions_m[galaxie_index])
    galaxy_velocity = vitesse_galaxie_m_s or Vecteur3.from_iterable(scenario.galaxies.backend.velocities_m_s[galaxie_index])

    root = CadreInertielRelatif("Cadre instantane du groupe", id="transition-group")
    local = CadreInertielRelatif(
        f"Cadre instantane galaxie {galaxie_index + 1}",
        root.id,
        EvenementMinkowski(instant.seconds, galaxy_position),
        galaxy_velocity,
        id=f"transition-galaxy-{galaxie_index:03d}",
    )
    registry = RegistreCadresInertiels(root)
    registry.ajouter(local)
    event_group = EvenementMinkowski(instant.seconds, position_group)
    event_local = registry.transformer_evenement(event_group, root.id, local.id)
    p_group = Quadrimpulsion(energie_totale_relativiste(mass, momentum_group) / C, momentum_group)
    p_local = registry.transformer_quadrimpulsion(p_group, root.id, local.id)

    frame = referentiel_local or referentiel_local_trou_noir(galaxie_index)
    state = EtatPhysique(
        instant,
        referentiel=frame,
        massique=EtatMassique(GrandeurPhysique(mass, "kg")),
        relativiste=EtatCinematiqueRelativiste(event_local.position_m, p_local.impulsion, proper_time),
    )
    return EtatLocalTransitionGR(state, event_local.t_s, galaxie_index, event_local, p_local)


def materialiser_trou_noir_central(
    catalogue: CatalogueMultiGalaxies,
    galaxie_index: int,
    *,
    referentiel_local: Referentiel | None = None,
    spin_dimensionnel: float = 0.0,
) -> TrouNoir:
    if not 0 <= galaxie_index < catalogue.configuration.nombre_galaxies:
        raise IndexError(galaxie_index)
    if abs(spin_dimensionnel) > 1:
        raise ValueError("Dimensionless black-hole spin must satisfy |chi| <= 1")
    black_holes = catalogue.tranches["black_holes"]
    compact_index = black_holes.start + galaxie_index
    mass = float(catalogue.masses_kg[compact_index])
    rs = 2.0 * G * mass / (C * C)
    angular_momentum = spin_dimensionnel * G * mass * mass / C
    frame = referentiel_local or referentiel_local_trou_noir(galaxie_index)
    state = EtatPhysique(
        Instant(0.0),
        referentiel=frame,
        translation=EtatTranslationnel(Vecteur3.zero(), Vecteur3.zero()),
        massique=EtatMassique(GrandeurPhysique(mass, "kg")),
    )
    return TrouNoir(
        nom=f"Trou noir central galaxie {galaxie_index + 1}",
        etat_courant=state,
        rayon_reference=GrandeurPhysique(rs, "m"),
        id=catalogue.id_corps(compact_index),
        moment_cinetique_spin=Vecteur3(0.0, 0.0, angular_momentum),
    )


def materialiser_vaisseau_local(
    scenario: ScenarioMultiGalaxies,
    index_vaisseau: int,
    galaxie_index: int,
    instant: Instant,
    **kwargs,
) -> tuple[Vehicule, EtatLocalTransitionGR]:
    frame = kwargs.pop("referentiel_local", None) or referentiel_local_trou_noir(galaxie_index)
    local = etat_vaisseau_sr_dans_cadre_galaxie(
        scenario,
        index_vaisseau,
        galaxie_index,
        instant,
        referentiel_local=frame,
        **kwargs,
    )
    compact_index = scenario.catalogue.tranches["ships"].start + index_vaisseau
    ship = Vehicule(
        nom=f"Voyageur relativiste {index_vaisseau + 1}",
        etat_courant=local.etat_sr_local,
        rayon_reference=GrandeurPhysique(float(scenario.catalogue.rayons_m[compact_index]), "m"),
        id=scenario.catalogue.id_vaisseau(index_vaisseau),
    )
    return ship, local


def metrique_trou_noir_central(
    catalogue: CatalogueMultiGalaxies,
    galaxie_index: int,
    *,
    spin_dimensionnel: float = 0.0,
):
    black_hole = materialiser_trou_noir_central(
        catalogue,
        galaxie_index,
        spin_dimensionnel=spin_dimensionnel,
    )
    return metrique_pour_trou_noir(black_hole)
