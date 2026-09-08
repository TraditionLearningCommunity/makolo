"""Numerical integrators for the dynamic universe state."""
from __future__ import annotations
from abc import ABC,abstractmethod
from dataclasses import dataclass
from ..states import DeriveeEtat,EtatPhysique,EtatMassique,EtatTranslationnel,EtatRotationnel,EtatElectrique
from ..systems import Univers
from ..values import GrandeurPhysique,Instant
from .engine import MoteurPhysique

def _capture(univers:Univers)->dict[str,EtatPhysique]:return {b.id:b.etat().copier() for b in univers.corps_physiques if b.actif}
def _install(univers:Univers,states:dict[str,EtatPhysique])->None:
    for b in univers.corps_physiques:
        if b.id in states:b.etat_courant=states[b.id]
def _apply_stage(base:dict[str,EtatPhysique],k:dict[str,DeriveeEtat],h:float,stage_time:float)->dict[str,EtatPhysique]:
    result={}
    for body_id,state in base.items():
        d=k[body_id];new=state.copier();new.instant=Instant(stage_time)
        if state.translation is not None:new.translation=EtatTranslationnel(state.translation.position+d.d_position*h,state.translation.vitesse+d.d_vitesse*h)
        if state.rotation is not None:new.rotation=EtatRotationnel((state.rotation.orientation+d.d_orientation*h).normalized(),state.rotation.vitesse_angulaire+d.d_vitesse_angulaire*h)
        if state.massique is not None:new.massique=EtatMassique(GrandeurPhysique(max(0,state.massique.masse.value+d.d_masse*h),state.massique.masse.unit,state.massique.masse.uncertainty))
        if state.electrique is not None:new.electrique=EtatElectrique(GrandeurPhysique(state.electrique.charge_nette.value+d.d_charge*h,state.electrique.charge_nette.unit),state.electrique.moment_dipolaire_electrique)
        result[body_id]=new
    return result
def _combine_rk4(base,ks,dt,final_time):
    k1,k2,k3,k4=ks;result={}
    for body_id,state in base.items():
        new=state.copier();new.instant=Instant(final_time);d1,d2,d3,d4=k1[body_id],k2[body_id],k3[body_id],k4[body_id]
        if state.translation is not None:
            dp=(d1.d_position+2*d2.d_position+2*d3.d_position+d4.d_position)*(dt/6);dv=(d1.d_vitesse+2*d2.d_vitesse+2*d3.d_vitesse+d4.d_vitesse)*(dt/6)
            new.translation=EtatTranslationnel(state.translation.position+dp,state.translation.vitesse+dv)
        if state.rotation is not None:
            dq=(d1.d_orientation+2*d2.d_orientation+2*d3.d_orientation+d4.d_orientation)*(dt/6);dw=(d1.d_vitesse_angulaire+2*d2.d_vitesse_angulaire+2*d3.d_vitesse_angulaire+d4.d_vitesse_angulaire)*(dt/6)
            new.rotation=EtatRotationnel((state.rotation.orientation+dq).normalized(),state.rotation.vitesse_angulaire+dw)
        if state.massique is not None:
            dm=(d1.d_masse+2*d2.d_masse+2*d3.d_masse+d4.d_masse)*(dt/6);new.massique=EtatMassique(GrandeurPhysique(max(0,state.massique.masse.value+dm),state.massique.masse.unit))
        if state.electrique is not None:
            dqv=(d1.d_charge+2*d2.d_charge+2*d3.d_charge+d4.d_charge)*(dt/6);new.electrique=EtatElectrique(GrandeurPhysique(state.electrique.charge_nette.value+dqv,state.electrique.charge_nette.unit),state.electrique.moment_dipolaire_electrique)
        result[body_id]=new
    return result
class IntegrateurNumerique(ABC):
    nom:str
    @abstractmethod
    def avancer(self,univers:Univers,moteur:MoteurPhysique,instant:Instant,dt:float)->None:raise NotImplementedError
@dataclass(slots=True)
class IntegrateurEuler(IntegrateurNumerique):
    nom:str="Euler explicite"
    def avancer(self,univers,moteur,instant,dt):
        base=_capture(univers);k1=moteur.calculer_derivees(univers,instant);_install(univers,_apply_stage(base,k1,dt,instant.seconds+dt))
@dataclass(slots=True)
class IntegrateurRK4(IntegrateurNumerique):
    nom:str="Runge-Kutta 4"
    def avancer(self,univers,moteur,instant,dt):
        base=_capture(univers)
        try:
            k1=moteur.calculer_derivees(univers,instant);_install(univers,_apply_stage(base,k1,dt*.5,instant.seconds+dt*.5));k2=moteur.calculer_derivees(univers,Instant(instant.seconds+dt*.5))
            _install(univers,_apply_stage(base,k2,dt*.5,instant.seconds+dt*.5));k3=moteur.calculer_derivees(univers,Instant(instant.seconds+dt*.5));_install(univers,_apply_stage(base,k3,dt,instant.seconds+dt));k4=moteur.calculer_derivees(univers,Instant(instant.seconds+dt))
            _install(univers,_combine_rk4(base,(k1,k2,k3,k4),dt,instant.seconds+dt))
        except Exception:_install(univers,base);raise
@dataclass(slots=True)
class IntegrateurSymplectique(IntegrateurNumerique):
    nom:str="Velocity Verlet symplectique"
    def avancer(self,univers,moteur,instant,dt):
        base=_capture(univers);k0=moteur.calculer_derivees(univers,instant);mid={k:v.copier() for k,v in base.items()}
        for body_id,state in mid.items():
            if state.translation is None:continue
            vh=state.translation.vitesse+k0[body_id].d_vitesse*(.5*dt);state.translation=EtatTranslationnel(state.translation.position+vh*dt,vh);state.instant=Instant(instant.seconds+dt)
        _install(univers,mid);k1=moteur.calculer_derivees(univers,Instant(instant.seconds+dt))
        for b in univers.corps_physiques:
            if b.id not in mid or b.etat().translation is None:continue
            t=b.etat().translation;b.etat_courant.translation=EtatTranslationnel(t.position,t.vitesse+k1[b.id].d_vitesse*(.5*dt));b.etat_courant.instant=Instant(instant.seconds+dt)
