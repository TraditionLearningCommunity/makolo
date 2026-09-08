from __future__ import annotations
from dataclasses import dataclass,field
from typing import Callable
from ..events import EvenementPhysique
from ..systems import Univers
from .clock import HorlogeSimulation
from .configuration import ConfigurationPhysique
from .diagnostics import ControlePhysique
from .engine import MoteurPhysique
from .integrators import IntegrateurNumerique,IntegrateurRK4
from .managers import GestionnaireEvenements
from .snapshot import Snapshot
@dataclass(slots=True)
class Simulation:
    univers:Univers;horloge:HorlogeSimulation;configuration:ConfigurationPhysique
    integrateur:IntegrateurNumerique=field(default_factory=IntegrateurRK4);moteur:MoteurPhysique|None=None
    gestionnaire_evenements:GestionnaireEvenements=field(default_factory=GestionnaireEvenements);controle:ControlePhysique=field(default_factory=ControlePhysique)
    snapshots:list[Snapshot]=field(default_factory=list);pas_effectues:int=0
    def __post_init__(self)->None:
        if self.moteur is None:self.moteur=MoteurPhysique(self.configuration)
    def avancer(self,dt:float|None=None)->list[EvenementPhysique]:
        if self.moteur is None:raise RuntimeError("Physics engine is not configured")
        step=self.horloge.pas_temps.seconds if dt is None else float(dt);t0=self.horloge.instant_courant
        self.integrateur.avancer(self.univers,self.moteur,t0,step);self.horloge.avancer(step);self.pas_effectues+=1
        events=self.gestionnaire_evenements.detecter(self.univers,self.horloge.instant_courant) if self.configuration.collisions_actives else []
        if self.configuration.conserver_historique and self.pas_effectues%max(1,self.configuration.enregistrer_tous_les_n_pas)==0:
            self.snapshots.append(Snapshot.capturer(self.univers,self.horloge.instant_courant))
            for body in self.univers.corps_physiques:body.enregistrer_etat()
        return events
    def executer(self,duree:float,dt:float|None=None,callback:Callable[["Simulation"],None]|None=None)->None:
        step=self.horloge.pas_temps.seconds if dt is None else float(dt)
        if step<=0:raise ValueError("Time step must be positive")
        target=self.horloge.instant_courant.seconds+duree
        while self.horloge.instant_courant.seconds<target-1e-12:
            self.avancer(min(step,target-self.horloge.instant_courant.seconds))
            if callback is not None:callback(self)
    def diagnostic(self)->dict[str,object]:return self.controle.mesurer(self.univers)
