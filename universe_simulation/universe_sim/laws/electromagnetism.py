"""Classical electromagnetic interaction using the Lorentz force."""
from __future__ import annotations
from dataclasses import dataclass
from ..effects import EffetPhysique, Force
from ..fields import ChampElectromagnetique
from ..systems import Univers
from ..values import Instant
from .base import ModelePhysique

@dataclass(slots=True)
class ElectromagnetismeClassique(ModelePhysique):
    champ: ChampElectromagnetique | None = None
    nom: str = "Electromagnetisme classique"
    domaine_validite: str = "classical Lorentz force"
    niveau_fidelite: str = "prescribed electromagnetic field"
    def evaluer(self, univers: Univers, instant: Instant, gestionnaire_interactions: object | None = None) -> list[EffetPhysique]:
        if self.champ is None: return []
        effects=[]
        for body in univers.corps_physiques:
            state=body.etat()
            if not body.actif or state.translation is None: continue
            q=body.charge().value
            if q==0: continue
            E,B=self.champ.evaluer(state.translation.position,instant)
            force=(E+state.translation.vitesse.cross(B))*q
            effects.append(Force(cible_id=body.id,instant=instant,loi_origine=self.nom,vecteur=force))
        return effects
