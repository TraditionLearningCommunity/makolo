from dataclasses import dataclass
from ..states import EtatPhysique
from ..systems import Univers
from ..values import Instant
@dataclass(slots=True)
class Snapshot:
    instant:Instant; etats:dict[str,EtatPhysique]
    @staticmethod
    def capturer(univers:Univers,instant:Instant)->"Snapshot":return Snapshot(instant,{b.id:b.etat().copier() for b in univers.corps_physiques})
