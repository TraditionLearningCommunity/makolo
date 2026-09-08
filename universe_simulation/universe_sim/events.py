"""Discrete physical and observational events."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from .values import Instant, Vecteur3


class TypeEvenement(str, Enum):
    COLLISION = "collision"
    IMPACT = "impact"
    FUSION = "fusion"
    FRAGMENTATION = "fragmentation"
    SEPARATION = "separation"
    CAPTURE_GRAVITATIONNELLE = "capture_gravitationnelle"
    EJECTION = "ejection"
    TRANSIT = "transit"
    OCCULTATION = "occultation"
    ECLIPSE = "eclipse"


@dataclass(slots=True)
class EvenementPhysique:
    type: TypeEvenement
    instant: Instant
    participants_ids: tuple[str, ...]
    position: Vecteur3 | None = None
    details: dict[str, float | str | bool] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
