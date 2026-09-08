from dataclasses import dataclass

from ..spacetime import EPOQUE_SIMULATION, EpoqueReference
from ..values import Duree, Instant


@dataclass(slots=True)
class HorlogeSimulation:
    instant_courant: Instant
    pas_temps: Duree
    direction: int = 1
    echelle_temps: float = 1.0
    epoque_reference: EpoqueReference = EPOQUE_SIMULATION

    def avancer(self, dt: float | None = None) -> Instant:
        delta = self.pas_temps.seconds if dt is None else float(dt)
        self.instant_courant = Instant(self.instant_courant.seconds + self.direction * delta)
        return self.instant_courant
