"""Atmospheric drag, radiation pressure, collision and propulsion models."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
from ..bodies import CorpsPhysique
from ..constants import C
from ..effects import EffetPhysique, Force, VariationMasse
from ..events import EvenementPhysique, TypeEvenement
from ..fields import Atmosphere, Rayonnement
from ..systems import Univers
from ..values import Instant, Vecteur3
from .base import ModelePhysique

@dataclass(slots=True)
class ModeleTraineeAtmospherique(ModelePhysique):
    corps_hote_id: str=""
    atmosphere: Atmosphere|None=None
    nom: str="Trainee atmospherique"
    domaine_validite: str="continuum drag approximation"
    niveau_fidelite: str="quadratic drag"
    def evaluer(self, univers: Univers, instant: Instant, gestionnaire_interactions: object|None=None) -> list[EffetPhysique]:
        if self.atmosphere is None: return []
        host=univers.trouver_corps(self.corps_hote_id); hs=host.etat().translation
        if hs is None: return []
        effects=[]
        for body in univers.corps_physiques:
            if body.id==host.id or not body.actif or body.etat().translation is None: continue
            if body.coefficient_trainee is None or body.surface_reference is None: continue
            bt=body.etat().translation; rel_pos=bt.position-hs.position
            rho=self.atmosphere.densite(rel_pos,instant); fluid_velocity=hs.vitesse+self.atmosphere.vitesse_fluide(rel_pos,instant)
            vrel=bt.vitesse-fluid_velocity; speed=vrel.norm()
            if speed==0 or rho==0: continue
            magnitude=0.5*rho*body.coefficient_trainee*body.surface_reference*speed*speed
            effects.append(Force(cible_id=body.id,source_id=host.id,instant=instant,loi_origine=self.nom,vecteur=-vrel.normalized()*magnitude))
        return effects

@dataclass(slots=True)
class ModelePressionRadiative(ModelePhysique):
    source_id: str=""; rayonnement: Rayonnement|None=None; coefficient_reflexion: float=1.0
    nom: str="Pression de radiation"; domaine_validite: str="geometric radiation pressure"; niveau_fidelite: str="inverse-square flux"
    def evaluer(self, univers: Univers, instant: Instant, gestionnaire_interactions: object|None=None) -> list[EffetPhysique]:
        if self.rayonnement is None: return []
        source=univers.trouver_corps(self.source_id); st=source.etat().translation
        if st is None: return []
        effects=[]
        for body in univers.corps_physiques:
            if body.id==source.id or body.surface_reference is None or body.etat().translation is None: continue
            rel=body.etat().translation.position-st.position
            if rel.norm2()==0: continue
            flux=self.rayonnement.flux_a(body.etat().translation.position,instant)
            magnitude=self.coefficient_reflexion*flux*body.surface_reference/C
            effects.append(Force(cible_id=body.id,source_id=source.id,instant=instant,loi_origine=self.nom,vecteur=rel.normalized()*magnitude))
        return effects

@dataclass(slots=True)
class ModeleCollision(ModelePhysique):
    coefficient_restitution: float=1.0
    nom: str="Detection de collision"; domaine_validite: str="spherical contact detection"; niveau_fidelite: str="event detection"
    def evaluer(self, univers: Univers, instant: Instant, gestionnaire_interactions: object|None=None) -> list[EffetPhysique]: return []
    def detecter_evenements(self, univers: Univers, instant: Instant) -> list[EvenementPhysique]:
        events=[]; bodies=[b for b in univers.corps_physiques if b.actif and b.rayon_reference is not None and b.etat().translation is not None]
        for i in range(len(bodies)):
            for j in range(i+1,len(bodies)):
                a,b=bodies[i],bodies[j]; pa=a.etat().translation.position; pb=b.etat().translation.position
                if pa.distance_to(pb)<=a.rayon_reference.value+b.rayon_reference.value:
                    events.append(EvenementPhysique(TypeEvenement.COLLISION,instant,(a.id,b.id),(pa+pb)*0.5,{"restitution":self.coefficient_restitution}))
        return events

@dataclass(slots=True)
class CommandePropulsive:
    poussee: Callable[[Instant,CorpsPhysique],Vecteur3]
    debit_massique: Callable[[Instant,CorpsPhysique],float]=lambda _t,_b:0.0

@dataclass(slots=True)
class ModelePropulsion(ModelePhysique):
    commandes: dict[str,CommandePropulsive]=field(default_factory=dict)
    nom: str="Propulsion macroscopique"; domaine_validite: str="prescribed thrust and propellant mass flow"; niveau_fidelite: str="external physical thrust"
    def evaluer(self, univers: Univers, instant: Instant, gestionnaire_interactions: object|None=None) -> list[EffetPhysique]:
        effects=[]
        for body_id,command in self.commandes.items():
            body=univers.trouver_corps(body_id); thrust=command.poussee(instant,body)
            if thrust.norm2()>0: effects.append(Force(cible_id=body.id,instant=instant,loi_origine=self.nom,vecteur=thrust))
            dm_dt=command.debit_massique(instant,body)
            if dm_dt!=0: effects.append(VariationMasse(cible_id=body.id,instant=instant,loi_origine=self.nom,dm_dt=dm_dt))
        return effects
