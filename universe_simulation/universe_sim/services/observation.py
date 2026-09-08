from __future__ import annotations
from math import asin,atan2
from ..bodies import CorpsPhysique
from ..constants import C
from ..observation import Constellation,Observation,Observateur
from ..values import Instant,Vecteur3

def direction_apparente(observateur:Observateur,cible:CorpsPhysique,instant:Instant,corriger_temps_lumiere:bool=True):
    state=cible.etat()
    if state.translation is None: raise ValueError("Observed target requires a translational state")
    target=state.translation.position; rel=target-observateur.position; distance=rel.norm()
    if corriger_temps_lumiere and distance>0:
        target=target-state.translation.vitesse*(distance/C); rel=target-observateur.position; distance=rel.norm()
    return rel.normalized(),distance
def direction_vers_radec(direction:Vecteur3):
    d=direction.normalized(); return atan2(d.y,d.x)%(2*3.141592653589793),asin(max(-1,min(1,d.z)))
def effectuer_observation(observateur:Observateur,cible:CorpsPhysique,instant:Instant,corriger_temps_lumiere:bool=True)->Observation:
    direction,distance=direction_apparente(observateur,cible,instant,corriger_temps_lumiere); ra,dec=direction_vers_radec(direction)
    return Observation(observateur,cible,instant,direction,distance,ra,dec)
def determiner_constellation(observation:Observation,constellations:list[Constellation])->Constellation|None:
    if observation.ascension_droite is None or observation.declinaison is None: return None
    return next((c for c in constellations if c.contient(observation.ascension_droite,observation.declinaison)),None)
def separation_angulaire(a:Vecteur3,b:Vecteur3)->float: return a.angle_with(b)
