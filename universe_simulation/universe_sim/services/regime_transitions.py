"""Explicit conversions between kinematic representations.

These functions convert state representation; they do not silently decide
which physical regime should be used. Curved-space-time conversion requires an
explicit metric/chart because a coordinate velocity is not an observer-
invariant physical velocity.
"""
from __future__ import annotations

from math import sqrt

from ..constants import C
from ..metrics import Coordonnees4, Metrique4D
from ..relativistic_state import EtatCinematiqueRelativiste, EtatSpatioTemporelRelativiste, TypeCourbeCausale
from ..states import EtatPhysique, EtatTranslationnel
from ..values import Vecteur3


def classique_vers_sr(etat: EtatPhysique) -> EtatPhysique:
    if etat.translation is None:
        raise ValueError("Classical-to-SR conversion requires a classical translational state")
    if etat.massique is None or etat.massique.masse.value <= 0:
        raise ValueError("Classical-to-SR conversion requires positive rest mass")
    result = etat.copier()
    translation = result.translation
    assert translation is not None
    result.translation = None
    result.relativiste = EtatCinematiqueRelativiste.depuis_vitesse(
        translation.position,
        translation.vitesse,
        result.massique.masse.value,
        0.0,
    )
    return result


def sr_vers_classique(etat: EtatPhysique, beta_max: float = 0.01) -> EtatPhysique:
    """Convert an SR state to Newtonian representation only below a beta guard."""
    if not 0 < beta_max < 1:
        raise ValueError("Classical conversion beta guard must lie in (0,1)")
    if etat.relativiste is None:
        raise ValueError("SR-to-classical conversion requires SR kinematics")
    if etat.massique is None or etat.massique.masse.value <= 0:
        raise ValueError("SR-to-classical conversion requires positive rest mass")
    velocity = etat.relativiste.vitesse(etat.massique.masse.value)
    beta = velocity.norm() / C
    if beta > beta_max:
        raise ValueError(
            f"Refusing Newtonian representation at beta={beta:.6g}; guard is beta<={beta_max:.6g}"
        )
    result = etat.copier()
    rel = result.relativiste
    assert rel is not None
    result.relativiste = None
    result.translation = EtatTranslationnel(rel.position, velocity)
    return result


def tangente_depuis_vitesse_coordonnees(
    metrique: Metrique4D,
    coordonnees_m: Coordonnees4,
    vitesse_coordonnees_m_s: Vecteur3,
) -> Coordonnees4:
    """Build a normalized timelike tangent preserving a chart-coordinate velocity.

    If ``w=(1,v/c)``, a timelike worldline requires ``g(w,w)<0``. The returned
    tangent is ``u=w/sqrt(-g(w,w))`` and therefore satisfies ``g(u,u)=-1``.
    """
    direction: Coordonnees4 = (
        1.0,
        vitesse_coordonnees_m_s.x / C,
        vitesse_coordonnees_m_s.y / C,
        vitesse_coordonnees_m_s.z / C,
    )
    norm = metrique.contracter(coordonnees_m, direction, direction)
    if norm >= 0:
        raise ValueError("Requested coordinate velocity is not timelike in the selected metric/chart")
    scale = 1.0 / sqrt(-norm)
    return tuple(scale * value for value in direction)  # type: ignore[return-value]


def vers_espace_temps_courbe(
    etat: EtatPhysique,
    metrique: Metrique4D,
    *,
    temps_coordonne_s: float | None = None,
    carte_coordonnees: str | None = None,
    temps_propre_initial_s: float | None = None,
) -> EtatPhysique:
    """Embed a classical/SR coordinate state into an explicit curved chart.

    The position and velocity are interpreted as coordinates of the selected
    chart. This is not a local-observer Lorentz transformation. For an SR input,
    accumulated proper time is preserved by default; for a classical input it
    starts at zero unless explicitly supplied.
    """
    if etat.espace_temps is not None:
        raise ValueError("State already uses curved-space-time kinematics")
    position = etat.position()
    velocity = etat.vitesse()
    if position is None or velocity is None:
        raise ValueError("Curved-space-time embedding requires position and coordinate velocity")
    coordinate_time = etat.instant.seconds if temps_coordonne_s is None else float(temps_coordonne_s)
    x: Coordonnees4 = (C * coordinate_time, position.x, position.y, position.z)
    tangent = tangente_depuis_vitesse_coordonnees(metrique, x, velocity)
    if temps_propre_initial_s is None:
        proper_time = 0.0 if etat.relativiste is None else etat.relativiste.temps_propre_s
    else:
        proper_time = float(temps_propre_initial_s)
    if proper_time < 0:
        raise ValueError("Initial proper time cannot be negative")

    result = etat.copier()
    result.translation = None
    result.relativiste = None
    result.espace_temps = EtatSpatioTemporelRelativiste(
        x,
        tangent,
        0.0,
        TypeCourbeCausale.TEMPORELLE,
        proper_time,
        carte_coordonnees or getattr(metrique, "coordonnees", "ct,x,y,z"),
    )
    return result
