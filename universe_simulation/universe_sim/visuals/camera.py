"""Cinematic camera paths. They affect presentation only, never physics."""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, log

from ..constants import AU
from ..values import Vecteur3
from .models import SequenceVisuelle
from .scales import EchelleVue, position_focus, resoudre_span


@dataclass(frozen=True, slots=True)
class EtatCamera:
    centre: Vecteur3
    span_m: float
    azimut_deg: float
    elevation_deg: float


@dataclass(frozen=True, slots=True)
class CleTour:
    fraction: float
    focus: str | None
    span_m: float
    azimut_deg: float
    elevation_deg: float


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_log(a: float, b: float, t: float) -> float:
    return exp(_lerp(log(max(a, 1.0)), log(max(b, 1.0)), t))


def _lerp_vecteur(a: Vecteur3, b: Vecteur3, t: float) -> Vecteur3:
    return a * (1.0 - t) + b * t


def _cles_tour(sequence: SequenceVisuelle, span_base: float, focus_final: str | None) -> tuple[CleTour, ...]:
    noms = sequence.corps_par_nom()
    if "Soleil" in noms and "Terre" in noms:
        return (
            CleTour(0.00, "Soleil", max(span_base, 32.0 * AU), 30.0, 22.0),
            CleTour(0.25, "Soleil", max(span_base, 32.0 * AU), 100.0, 28.0),
            CleTour(0.48, "Soleil", 2.2 * AU, 170.0, 30.0),
            CleTour(0.60, "Soleil", 2.2 * AU, 215.0, 24.0),
            CleTour(0.78, "Terre", 5.5e8, 285.0, 20.0),
            CleTour(1.00, focus_final or "Terre", 5.5e8, 385.0, 28.0),
        )
    return (
        CleTour(0.0, focus_final, span_base, 30.0, 24.0),
        CleTour(1.0, focus_final, span_base, 390.0, 28.0),
    )


def construire_plan_camera(
    sequence: SequenceVisuelle,
    echelle: EchelleVue,
    focus: str | None = None,
    mode: str = "orbit",
) -> tuple[EtatCamera, ...]:
    if mode not in {"static", "follow", "orbit", "tour"}:
        raise ValueError(f"Unknown camera mode: {mode}")
    if not sequence.frames:
        return tuple()

    focus_resolu = focus if focus is not None else echelle.focus_defaut
    span_base = resoudre_span(sequence, echelle, focus_resolu)
    total = max(1, len(sequence.frames) - 1)

    if mode != "tour":
        resultats = []
        for index in range(len(sequence.frames)):
            fraction = index / total
            centre = position_focus(sequence, index, focus_resolu) if mode in {"follow", "orbit"} else position_focus(sequence, 0, focus_resolu)
            azimut = 35.0 if mode in {"static", "follow"} else 35.0 + 360.0 * fraction
            elevation = 24.0 if mode != "orbit" else 24.0 + 6.0 * (1.0 - abs(2.0 * fraction - 1.0))
            resultats.append(EtatCamera(centre, span_base, azimut, elevation))
        return tuple(resultats)

    cles = _cles_tour(sequence, span_base, focus_resolu)
    resultats = []
    for index in range(len(sequence.frames)):
        fraction = index / total
        gauche = cles[0]
        droite = cles[-1]
        for a, b in zip(cles, cles[1:]):
            if a.fraction <= fraction <= b.fraction:
                gauche, droite = a, b
                break
        largeur = max(droite.fraction - gauche.fraction, 1e-12)
        local = _smoothstep((fraction - gauche.fraction) / largeur)
        centre_a = position_focus(sequence, index, gauche.focus)
        centre_b = position_focus(sequence, index, droite.focus)
        resultats.append(
            EtatCamera(
                centre=_lerp_vecteur(centre_a, centre_b, local),
                span_m=_lerp_log(gauche.span_m, droite.span_m, local),
                azimut_deg=_lerp(gauche.azimut_deg, droite.azimut_deg, local),
                elevation_deg=_lerp(gauche.elevation_deg, droite.elevation_deg, local),
            )
        )
    return tuple(resultats)
