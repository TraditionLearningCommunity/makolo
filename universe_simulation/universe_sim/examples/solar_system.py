from __future__ import annotations
from math import sqrt
from ..bodies import Etoile,Planete,SatelliteNaturel
from ..constants import AU,EARTH_MASS,EARTH_RADIUS,G,MOON_MASS,MOON_RADIUS,SOLAR_MASS,SOLAR_RADIUS
from ..laws.gravity import ModeleGravitationPonctuelle
from ..simulation import ConfigurationPhysique,HorlogeSimulation,IntegrateurRK4,IntegrateurSymplectique,Simulation
from ..spacetime import REFERENTIEL_INERTIEL
from ..states import EtatMassique,EtatPhysique,EtatTranslationnel
from ..systems import SystemePlanetaire,SystemeStellaire,Univers
from ..values import Duree,GrandeurPhysique,Instant,Vecteur3
MOON_DISTANCE=384_400_000.0
def _state(mass,position,velocity):return EtatPhysique(instant=Instant(0),referentiel=REFERENTIEL_INERTIEL,translation=EtatTranslationnel(position,velocity),massique=EtatMassique(GrandeurPhysique(mass,"kg")))
def construire_systeme_solaire_minimal(dt:float=3600.0,integrateur:str="rk4")->Simulation:
    earth_speed=sqrt(G*SOLAR_MASS/AU);moon_speed_rel=sqrt(G*EARTH_MASS/MOON_DISTANCE);earth_velocity=Vecteur3(0,earth_speed,0);moon_velocity=Vecteur3(0,earth_speed+moon_speed_rel,0);sun_velocity=-(earth_velocity*EARTH_MASS+moon_velocity*MOON_MASS)/SOLAR_MASS
    soleil=Etoile(nom="Soleil",etat_courant=_state(SOLAR_MASS,Vecteur3.zero(),sun_velocity),rayon_reference=GrandeurPhysique(SOLAR_RADIUS,"m"),luminosite=GrandeurPhysique(3.828e26,"W"),temperature_effective=GrandeurPhysique(5772,"K"),type_spectral="G2V")
    terre=Planete(nom="Terre",etat_courant=_state(EARTH_MASS,Vecteur3(AU,0,0),earth_velocity),rayon_reference=GrandeurPhysique(EARTH_RADIUS,"m"),rayon_equatorial=GrandeurPhysique(6_378_137,"m"),rayon_polaire=GrandeurPhysique(6_356_752.3,"m"),j2=1.08262668e-3,albedo=.306)
    lune=SatelliteNaturel(nom="Lune",etat_courant=_state(MOON_MASS,Vecteur3(AU+MOON_DISTANCE,0,0),moon_velocity),rayon_reference=GrandeurPhysique(MOON_RADIUS,"m"),corps_hote_id=terre.id)
    univers=Univers(nom="Soleil-Terre-Lune")
    for body in (soleil,terre,lune):univers.ajouter_corps(body)
    stellaire=SystemeStellaire("Systeme solaire minimal",membres=[soleil,terre,lune],gravitationnellement_lie=True);planetaire=SystemePlanetaire("Sous-systeme planetaire",membres=[soleil,terre,lune],gravitationnellement_lie=True,composantes_dominantes=[soleil.id]);stellaire.ajouter_sous_systeme(planetaire);univers.ajouter_systeme(stellaire);univers.ajouter_systeme(planetaire)
    config=ConfigurationPhysique([ModeleGravitationPonctuelle()],collisions_actives=True,conserver_historique=True);integ=IntegrateurSymplectique() if integrateur=="symplectic" else IntegrateurRK4()
    return Simulation(univers,HorlogeSimulation(Instant(0),Duree(dt)),config,integrateur=integ)
