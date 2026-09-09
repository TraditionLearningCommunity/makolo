"""Physical-dynamics regimes and simulation activity levels.

These enums describe *how* a physical state is evolved numerically. They are
not astronomical classifications of the body itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RegimeDynamique(str, Enum):
    CLASSIQUE = "classique"
    RELATIVISTE_SPECIAL = "relativiste_special"
    POST_NEWTONIEN_1PN = "post_newtonien_1pn"
    RELATIVISTE_GENERAL = "relativiste_general"
    # Backward-compatible name from the first migration iterations. A geodesic
    # is a free-fall trajectory, not the name of the physical theory/regime.
    GEODESIQUE = "relativiste_general"
    ANALYTIQUE = "analytique"

    @classmethod
    def _missing_(cls, value: object):
        if value == "geodesique":
            return cls.RELATIVISTE_GENERAL
        return None


class NiveauActiviteCalcul(str, Enum):
    ACTIVE = "active"
    ANALYTIC = "analytic"
    AGGREGATED = "aggregated"
    TRACER = "tracer"
    VISUAL_ONLY = "visual_only"


class TypeBackendEtat(str, Enum):
    OBJET = "object"
    TABLEAU = "array"


@dataclass(frozen=True, slots=True)
class PolitiqueDynamique:
    regime_par_defaut: RegimeDynamique = RegimeDynamique.CLASSIQUE
    selection_automatique: bool = False
    precision_relative_cible: float = 1e-9

    def __post_init__(self) -> None:
        if self.precision_relative_cible <= 0:
            raise ValueError("Target relative precision must be positive")
