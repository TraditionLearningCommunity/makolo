from dataclasses import dataclass,field
from itertools import combinations
from ..bodies import CorpsPhysique
from ..events import EvenementPhysique
from ..fields import ChampPhysique
from ..laws.environment import ModeleCollision
from ..systems import Univers
from ..values import Instant
@dataclass(slots=True)
class GestionnaireInteractions:
    distance_max:float|None=None
    def paires(self,corps:list[CorpsPhysique]):
        for a,b in combinations(corps,2):
            if self.distance_max is not None:
                ta,tb=a.etat().translation,b.etat().translation
                if ta is None or tb is None or ta.position.distance_to(tb.position)>self.distance_max: continue
            yield a,b
@dataclass(slots=True)
class GestionnaireChamps:
    champs:list[ChampPhysique]=field(default_factory=list)
    def ajouter(self,champ:ChampPhysique)->None:self.champs.append(champ)
@dataclass(slots=True)
class GestionnaireEvenements:
    modeles_collision:list[ModeleCollision]=field(default_factory=list); historique:list[EvenementPhysique]=field(default_factory=list)
    def detecter(self,univers:Univers,instant:Instant)->list[EvenementPhysique]:
        events=[]
        for model in self.modeles_collision:
            if model.active:events.extend(model.detecter_evenements(univers,instant))
        self.historique.extend(events);return events
