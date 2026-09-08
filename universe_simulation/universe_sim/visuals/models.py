"""Renderer-neutral visual data extracted from a physical simulation."""
from __future__ import annotations

from dataclasses import dataclass

from ..values import Vecteur3


@dataclass(frozen=True, slots=True)
class CorpsVisuel:
    id: str
    nom: str
    type_corps: str
    rayon_m: float | None
    masse_kg: float | None


@dataclass(frozen=True, slots=True)
class FrameVisuelle:
    instant_s: float
    positions: dict[str, Vecteur3]


@dataclass(frozen=True, slots=True)
class SequenceVisuelle:
    univers_nom: str
    corps: tuple[CorpsVisuel, ...]
    frames: tuple[FrameVisuelle, ...]
    pas_total: int

    def corps_par_id(self) -> dict[str, CorpsVisuel]:
        return {corps.id: corps for corps in self.corps}

    def corps_par_nom(self) -> dict[str, CorpsVisuel]:
        return {corps.nom: corps for corps in self.corps}

    def trouver_id(self, identifiant_ou_nom: str) -> str:
        for corps in self.corps:
            if corps.id == identifiant_ou_nom or corps.nom == identifiant_ou_nom:
                return corps.id
        raise KeyError(identifiant_ou_nom)
