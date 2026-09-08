from __future__ import annotations
from dataclasses import dataclass,field
from ..effects import Couple,Force,VariationMasse
from ..states import DeriveeEtat
from ..systems import Univers
from ..values import Instant
from .configuration import ConfigurationPhysique
from .managers import GestionnaireInteractions
@dataclass(slots=True)
class MoteurPhysique:
    configuration:ConfigurationPhysique
    gestionnaire_interactions:GestionnaireInteractions=field(default_factory=GestionnaireInteractions)
    def evaluer_effets(self,univers:Univers,instant:Instant):
        effects=[]
        for model in self.configuration.modeles_actifs():effects.extend(model.evaluer(univers,instant,self.gestionnaire_interactions))
        return effects
    def calculer_derivees(self,univers:Univers,instant:Instant)->dict[str,DeriveeEtat]:
        derivatives={};by_id={b.id:b for b in univers.corps_physiques}
        for body in univers.corps_physiques:
            state=body.etat()
            if not body.actif:continue
            d=DeriveeEtat()
            if state.translation is not None:d.d_position=state.translation.vitesse
            if state.rotation is not None:d.d_orientation=state.rotation.orientation.derivative(state.rotation.vitesse_angulaire)
            derivatives[body.id]=d
        for effect in self.evaluer_effets(univers,instant):
            if effect.cible_id not in derivatives:continue
            body=by_id[effect.cible_id];d=derivatives[effect.cible_id]
            if isinstance(effect,Force):
                mass=body.masse().value
                if mass<=0:raise ValueError(f"Positive mass required to apply force to {body.nom}")
                d.d_vitesse=d.d_vitesse+effect.vecteur/mass
            elif isinstance(effect,Couple):
                mass=body.masse().value;radius=body.rayon_reference.value if body.rayon_reference is not None else None
                if radius is not None and mass>0:d.d_vitesse_angulaire=d.d_vitesse_angulaire+effect.moment/(0.4*mass*radius*radius)
            elif isinstance(effect,VariationMasse):d.d_masse+=effect.dm_dt
        return derivatives
