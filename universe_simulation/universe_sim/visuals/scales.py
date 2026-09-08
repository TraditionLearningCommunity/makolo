"""Multi-scale camera presets for astronomical scenes."""
from __future__ import annotations

from dataclasses import dataclass

from ..constants import AU
from ..values import Vecteur3
from .models import SequenceVisuelle


@dataclass(frozen=True, slots=True)
class EchelleVue:
    nom: str
    span_m: float | None
    unite_m: float
    unite_label: str
    focus_defaut: str | None = None
    description: str = ""


ECHELLES: dict[str, EchelleVue] = {
    "auto": EchelleVue("auto", None, AU, "AU", None, "Fit all visible bodies."),
    "solar": EchelleVue("solar", 32.0 * AU, AU, "AU", "Soleil", "Whole Solar System through Neptune."),
    "inner": EchelleVue("inner", 2.2 * AU, AU, "AU", "Soleil", "Inner planets through Mars."),
    "earth-moon": EchelleVue("earth-moon", 5.5e8, 1_000.0, "km", "Terre", "Earth-Moon local system."),
    "earth-orbit": EchelleVue("earth-orbit", 6.0e7, 1_000.0, "km", "Terre", "Near-Earth orbital space."),
    "binary": EchelleVue("binary", 0.35 * AU, AU, "AU", None, "Compact binary-star view."),
}


def obtenir_echelle(nom: str) -> EchelleVue:
    try:
        return ECHELLES[nom]
    except KeyError as exc:
        raise ValueError(f"Unknown visual scale: {nom}") from exc


def position_focus(sequence: SequenceVisuelle, frame_index: int, focus: str | None) -> Vecteur3:
    if not focus:
        return Vecteur3.zero()
    corps_id = sequence.trouver_id(focus)
    return sequence.frames[frame_index].positions.get(corps_id, Vecteur3.zero())


def span_automatique(sequence: SequenceVisuelle, focus: str | None = None, marge: float = 1.15) -> float:
    if not sequence.frames:
        return AU
    maximum = 0.0
    for index, frame in enumerate(sequence.frames):
        centre = position_focus(sequence, index, focus)
        for position in frame.positions.values():
            maximum = max(maximum, position.distance_to(centre))
    return max(maximum * marge, 1.0)


def resoudre_span(sequence: SequenceVisuelle, echelle: EchelleVue, focus: str | None = None) -> float:
    return echelle.span_m if echelle.span_m is not None else span_automatique(sequence, focus or echelle.focus_defaut)
