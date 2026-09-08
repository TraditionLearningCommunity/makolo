from dataclasses import dataclass
from ..services.mechanics import energie_mecanique_totale,moment_cinetique_total,quantite_mouvement_totale
from ..systems import Univers
@dataclass(slots=True)
class ControlePhysique:
    energie_reference:float|None=None
    def mesurer(self,univers:Univers)->dict[str,object]:
        energy=energie_mecanique_totale(univers.corps_physiques)
        if self.energie_reference is None:self.energie_reference=energy
        drift=0.0 if self.energie_reference==0 else (energy-self.energie_reference)/abs(self.energie_reference)
        return {"energie_mecanique":energy,"derive_relative_energie":drift,"quantite_mouvement":quantite_mouvement_totale(univers.corps_physiques),"moment_cinetique":moment_cinetique_total(univers.corps_physiques)}
