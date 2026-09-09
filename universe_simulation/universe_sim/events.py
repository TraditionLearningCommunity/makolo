"""Discrete physical and simulation-control events."""
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
    ENTREE_SPHERE_INFLUENCE = "entree_sphere_influence"
    SORTIE_SPHERE_INFLUENCE = "sortie_sphere_influence"
    ENTREE_SYSTEME = "entree_systeme"
    SORTIE_SYSTEME = "sortie_systeme"
    ENTREE_GALAXIE = "entree_galaxie"
    SORTIE_GALAXIE = "sortie_galaxie"
    EPUISEMENT_PROPERGOL = "epuisement_propergol"
    ALLUMAGE_MOTEUR = "allumage_moteur"
    COUPURE_MOTEUR = "coupure_moteur"
    FRANCHISSEMENT_HORIZON = "franchissement_horizon"
    EFFONDREMENT_STELLAIRE = "effondrement_stellaire"
    FORMATION_RESIDU_COMPACT = "formation_residu_compact"
    DESTRUCTION = "destruction"


class TypeEvenementSimulation(str, Enum):
    CHANGEMENT_REGIME_DYNAMIQUE = "changement_regime_dynamique"
    MATERIALISATION_LOD = "materialisation_lod"
    DEMATERIALISATION_LOD = "dematerialisation_lod"


@dataclass(slots=True)
class EvenementPhysique:
    type: TypeEvenement
    instant: Instant
    participants_ids: tuple[str, ...]
    position: Vecteur3 | None = None
    details: dict[str, float | str | bool] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(slots=True)
class EvenementSimulation:
    type: TypeEvenementSimulation
    instant: Instant
    cible_id: str | None = None
    details: dict[str, float | str | bool] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
