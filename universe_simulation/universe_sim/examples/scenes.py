"""Ready-to-run physical scenes for demos and visualization."""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin, sqrt
from typing import Callable

from ..bodies import Etoile, Planete, SatelliteNaturel
from ..constants import AU, EARTH_MASS, EARTH_RADIUS, G, MOON_MASS, MOON_RADIUS, SOLAR_MASS, SOLAR_RADIUS
from ..laws.gravity import ModeleGravitationPonctuelle
from ..simulation import ConfigurationPhysique, HorlogeSimulation, IntegrateurRK4, IntegrateurSymplectique, Simulation
from ..spacetime import REFERENTIEL_INERTIEL
from ..states import EtatMassique, EtatPhysique, EtatTranslationnel
from ..systems import SystemePlanetaire, SystemeStellaire, Univers
from ..values import Duree, GrandeurPhysique, Instant, Vecteur3
from .catalogue import PLANETES_DEMO, PlaneteDemo
from .solar_system import construire_systeme_solaire_minimal

MOON_DISTANCE = 384_400_000.0


def _etat(masse_kg: float, position: Vecteur3, vitesse: Vecteur3) -> EtatPhysique:
    return EtatPhysique(
        instant=Instant(0.0),
        referentiel=REFERENTIEL_INERTIEL,
        translation=EtatTranslationnel(position, vitesse),
        massique=EtatMassique(GrandeurPhysique(masse_kg, "kg")),
    )


def _position_vitesse_circulaire(spec: PlaneteDemo) -> tuple[Vecteur3, Vecteur3]:
    phase = radians(spec.phase_deg)
    inclinaison = radians(spec.inclinaison_deg)
    r = spec.distance_m
    vitesse = sqrt(G * (SOLAR_MASS + spec.masse_kg) / r)
    position = Vecteur3(
        r * cos(phase),
        r * sin(phase) * cos(inclinaison),
        r * sin(phase) * sin(inclinaison),
    )
    vecteur_vitesse = Vecteur3(
        -vitesse * sin(phase),
        vitesse * cos(phase) * cos(inclinaison),
        vitesse * cos(phase) * sin(inclinaison),
    )
    return position, vecteur_vitesse


def _recentre_barycentre(corps: list[object]) -> None:
    masses = []
    total = 0.0
    somme_position = Vecteur3.zero()
    somme_vitesse = Vecteur3.zero()
    for body in corps:
        translation = body.etat().translation
        if translation is None:
            continue
        masse = body.masse().value
        masses.append((body, masse, translation))
        total += masse
        somme_position = somme_position + translation.position * masse
        somme_vitesse = somme_vitesse + translation.vitesse * masse
    if total <= 0:
        return
    centre = somme_position / total
    vitesse_centre = somme_vitesse / total
    for _body, _masse, translation in masses:
        translation.position = translation.position - centre
        translation.vitesse = translation.vitesse - vitesse_centre


def _simulation_depuis_corps(nom: str, corps: list[object], dt: float, integrateur: str) -> Simulation:
    univers = Univers(nom=nom)
    for body in corps:
        univers.ajouter_corps(body)
    systeme_stellaire = SystemeStellaire(nom, membres=list(corps), gravitationnellement_lie=True)
    etoiles = [body for body in corps if isinstance(body, Etoile)]
    systeme_planetaire = SystemePlanetaire(
        f"{nom} - systeme planetaire",
        membres=list(corps),
        gravitationnellement_lie=True,
        composantes_dominantes=[body.id for body in etoiles],
    )
    systeme_stellaire.ajouter_sous_systeme(systeme_planetaire)
    univers.ajouter_systeme(systeme_stellaire)
    univers.ajouter_systeme(systeme_planetaire)
    configuration = ConfigurationPhysique(
        [ModeleGravitationPonctuelle()],
        collisions_actives=True,
        conserver_historique=True,
    )
    integ = IntegrateurSymplectique() if integrateur == "symplectic" else IntegrateurRK4()
    return Simulation(univers, HorlogeSimulation(Instant(0.0), Duree(dt)), configuration, integrateur=integ)


def _construire_planetes(specs: tuple[PlaneteDemo, ...], include_moon: bool, dt: float, integrateur: str, nom: str) -> Simulation:
    soleil = Etoile(
        nom="Soleil",
        etat_courant=_etat(SOLAR_MASS, Vecteur3.zero(), Vecteur3.zero()),
        rayon_reference=GrandeurPhysique(SOLAR_RADIUS, "m"),
        luminosite=GrandeurPhysique(3.828e26, "W"),
        temperature_effective=GrandeurPhysique(5772.0, "K"),
        type_spectral="G2V",
    )
    corps: list[object] = [soleil]
    terre: Planete | None = None
    for spec in specs:
        position, vitesse = _position_vitesse_circulaire(spec)
        planete = Planete(
            nom=spec.nom,
            etat_courant=_etat(spec.masse_kg, position, vitesse),
            rayon_reference=GrandeurPhysique(spec.rayon_m, "m"),
            albedo=spec.albedo,
        )
        corps.append(planete)
        if spec.nom == "Terre":
            terre = planete

    if include_moon and terre is not None:
        etat_terre = terre.etat().translation
        assert etat_terre is not None
        phase = radians(40.0)
        inclinaison = radians(5.145)
        relative_position = Vecteur3(
            MOON_DISTANCE * cos(phase),
            MOON_DISTANCE * sin(phase) * cos(inclinaison),
            MOON_DISTANCE * sin(phase) * sin(inclinaison),
        )
        vitesse_lune = sqrt(G * (EARTH_MASS + MOON_MASS) / MOON_DISTANCE)
        relative_velocity = Vecteur3(
            -vitesse_lune * sin(phase),
            vitesse_lune * cos(phase) * cos(inclinaison),
            vitesse_lune * cos(phase) * sin(inclinaison),
        )
        lune = SatelliteNaturel(
            nom="Lune",
            etat_courant=_etat(
                MOON_MASS,
                etat_terre.position + relative_position,
                etat_terre.vitesse + relative_velocity,
            ),
            rayon_reference=GrandeurPhysique(MOON_RADIUS, "m"),
            corps_hote_id=terre.id,
        )
        corps.append(lune)

    _recentre_barycentre(corps)
    return _simulation_depuis_corps(nom, corps, dt, integrateur)


def construire_systeme_solaire_interieur(dt: float = 10_800.0, integrateur: str = "symplectic") -> Simulation:
    return _construire_planetes(PLANETES_DEMO[:4], True, dt, integrateur, "Systeme solaire interieur")


def construire_systeme_solaire_complet(dt: float = 21_600.0, integrateur: str = "symplectic") -> Simulation:
    return _construire_planetes(PLANETES_DEMO, True, dt, integrateur, "Systeme solaire complet")


def construire_systeme_terre_lune(dt: float = 900.0, integrateur: str = "symplectic") -> Simulation:
    distance = MOON_DISTANCE
    masse_totale = EARTH_MASS + MOON_MASS
    rayon_terre = distance * MOON_MASS / masse_totale
    rayon_lune = distance * EARTH_MASS / masse_totale
    omega = sqrt(G * masse_totale / distance**3)
    terre = Planete(
        nom="Terre",
        etat_courant=_etat(EARTH_MASS, Vecteur3(-rayon_terre, 0.0, 0.0), Vecteur3(0.0, -omega * rayon_terre, 0.0)),
        rayon_reference=GrandeurPhysique(EARTH_RADIUS, "m"),
        albedo=0.306,
    )
    lune = SatelliteNaturel(
        nom="Lune",
        etat_courant=_etat(MOON_MASS, Vecteur3(rayon_lune, 0.0, 0.0), Vecteur3(0.0, omega * rayon_lune, 0.0)),
        rayon_reference=GrandeurPhysique(MOON_RADIUS, "m"),
        corps_hote_id=terre.id,
    )
    return _simulation_depuis_corps("Systeme Terre-Lune", [terre, lune], dt, integrateur)


def construire_etoile_binaire(dt: float = 1_800.0, integrateur: str = "symplectic") -> Simulation:
    m1 = 1.10 * SOLAR_MASS
    m2 = 0.80 * SOLAR_MASS
    separation = 0.18 * AU
    total = m1 + m2
    r1 = separation * m2 / total
    r2 = separation * m1 / total
    omega = sqrt(G * total / separation**3)
    alpha = Etoile(
        nom="Alpha",
        etat_courant=_etat(m1, Vecteur3(-r1, 0.0, 0.0), Vecteur3(0.0, -omega * r1, 0.0)),
        rayon_reference=GrandeurPhysique(1.05 * SOLAR_RADIUS, "m"),
        luminosite=GrandeurPhysique(1.25 * 3.828e26, "W"),
        type_spectral="G",
    )
    beta = Etoile(
        nom="Beta",
        etat_courant=_etat(m2, Vecteur3(r2, 0.0, 0.0), Vecteur3(0.0, omega * r2, 0.0)),
        rayon_reference=GrandeurPhysique(0.78 * SOLAR_RADIUS, "m"),
        luminosite=GrandeurPhysique(0.42 * 3.828e26, "W"),
        type_spectral="K",
    )
    return _simulation_depuis_corps("Etoile binaire Alpha-Beta", [alpha, beta], dt, integrateur)


@dataclass(frozen=True, slots=True)
class DefinitionScene:
    nom: str
    constructeur: Callable[..., Simulation]
    description: str
    duree_jours_defaut: float
    dt_defaut: float
    echelle_defaut: str
    camera_defaut: str


SCENES: dict[str, DefinitionScene] = {
    "minimal": DefinitionScene("minimal", construire_systeme_solaire_minimal, "Sun-Earth-Moon compatibility scene.", 30.0, 3600.0, "inner", "orbit"),
    "inner": DefinitionScene("inner", construire_systeme_solaire_interieur, "Sun, four inner planets and Moon.", 365.0, 10_800.0, "inner", "orbit"),
    "solar": DefinitionScene("solar", construire_systeme_solaire_complet, "Sun, eight planets and Moon.", 365.0, 21_600.0, "solar", "tour"),
    "earth-moon": DefinitionScene("earth-moon", construire_systeme_terre_lune, "Earth-Moon barycentric two-body scene.", 30.0, 900.0, "earth-moon", "orbit"),
    "binary": DefinitionScene("binary", construire_etoile_binaire, "Compact binary-star scene.", 60.0, 1800.0, "binary", "orbit"),
}


def construire_scene(nom: str, dt: float | None = None, integrateur: str = "symplectic") -> Simulation:
    try:
        definition = SCENES[nom]
    except KeyError as exc:
        raise ValueError(f"Unknown scene: {nom}") from exc
    return definition.constructeur(dt=definition.dt_defaut if dt is None else dt, integrateur=integrateur)
