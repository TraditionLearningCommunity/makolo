"""Calculated physical effects. These are not permanent body attributes."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from .values import Instant, Vecteur3


@dataclass(slots=True)
class EffetPhysique:
    cible_id: str
    instant: Instant
    source_id: str | None = None
    loi_origine: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(slots=True)
class Force(EffetPhysique):
    vecteur: Vecteur3 = field(default_factory=Vecteur3.zero)
    point_application: Vecteur3 | None = None


@dataclass(slots=True)
class Couple(EffetPhysique):
    moment: Vecteur3 = field(default_factory=Vecteur3.zero)


@dataclass(slots=True)
class Impulsion(EffetPhysique):
    delta_quantite_mouvement: Vecteur3 = field(default_factory=Vecteur3.zero)


@dataclass(slots=True)
class VariationMasse(EffetPhysique):
    dm_dt: float = 0.0
