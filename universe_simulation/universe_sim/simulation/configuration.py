from dataclasses import dataclass,field
from ..laws.base import ModelePhysique
@dataclass(slots=True)
class ConfigurationPhysique:
    modeles:list[ModelePhysique]=field(default_factory=list); collisions_actives:bool=True; conserver_historique:bool=True; enregistrer_tous_les_n_pas:int=1
    def ajouter_modele(self,modele:ModelePhysique)->None:self.modeles.append(modele)
    def modeles_actifs(self):return tuple(m for m in self.modeles if m.active)
