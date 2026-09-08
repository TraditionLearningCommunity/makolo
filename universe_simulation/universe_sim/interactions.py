"""Physical interaction descriptors generated for calculations."""
from __future__ import annotations
from dataclasses import dataclass, field
from uuid import uuid4
from .bodies import CorpsPhysique
from .fields import ChampPhysique, MilieuPhysique, Rayonnement
from .values import Instant

@dataclass(slots=True)
class InteractionPhysique:
    participants: tuple[CorpsPhysique, ...]
    instant: Instant
    id: str = field(default_factory=lambda: str(uuid4()))

@dataclass(slots=True)
class InteractionGravitationnelle(InteractionPhysique):
    def __post_init__(self) -> None:
        if len(self.participants) != 2:
            raise ValueError("Newtonian pair interaction requires exactly two bodies")

@dataclass(slots=True)
class InteractionElectromagnetique(InteractionPhysique):
    champ: ChampPhysique | None = None
@dataclass(slots=True)
class InteractionContact(InteractionPhysique):
    restitution: float = 1.0
@dataclass(slots=True)
class InteractionFluide(InteractionPhysique):
    milieu: MilieuPhysique | None = None
@dataclass(slots=True)
class InteractionRadiative(InteractionPhysique):
    rayonnement: Rayonnement | None = None
@dataclass(slots=True)
class InteractionPropulsive(InteractionPhysique):
    commande_physique: object | None = None
