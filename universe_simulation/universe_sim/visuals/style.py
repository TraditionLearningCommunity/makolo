"""Astronomical presentation styles. Sizes are intentionally visual, not physical."""
from __future__ import annotations

from dataclasses import dataclass
from math import log10

from .models import CorpsVisuel


@dataclass(frozen=True, slots=True)
class StyleCorps:
    couleur: str
    taille_point: float
    facteur_sphere: float = 1.0


COULEURS_PAR_NOM = {
    "Soleil": "#FDB813",
    "Mercure": "#A7A7A7",
    "Venus": "#E7C27D",
    "Terre": "#4C9BFF",
    "Lune": "#D6D6D6",
    "Mars": "#D66B46",
    "Jupiter": "#D8A66A",
    "Saturne": "#E9D7A2",
    "Uranus": "#9DDDEB",
    "Neptune": "#4D6FFF",
    "Alpha": "#FFF1C1",
    "Beta": "#A9C8FF",
}

COULEURS_PAR_TYPE = {
    "Etoile": "#FFD166",
    "Planete": "#6FB1FF",
    "SatelliteNaturel": "#D8D8D8",
    "Asteroide": "#9C8D7A",
    "Comete": "#B8F2E6",
    "TrouNoir": "#2B2D42",
    "SatelliteArtificiel": "#F7F7F7",
    "SondeSpatiale": "#F7F7F7",
}


def style_corps(corps: CorpsVisuel) -> StyleCorps:
    couleur = COULEURS_PAR_NOM.get(corps.nom, COULEURS_PAR_TYPE.get(corps.type_corps, "#C7D2FE"))
    rayon = max(corps.rayon_m or 1.0, 1.0)
    taille = max(5.0, min(18.0, 5.0 + 1.7 * max(0.0, log10(rayon) - 5.0)))
    if corps.type_corps == "Etoile":
        taille = max(taille, 15.0)
    return StyleCorps(couleur, taille)


def rayon_affichage(corps: CorpsVisuel, span_m: float) -> float:
    """Return a visible sphere radius in metres for rendering only."""
    minimum = span_m * (0.006 if corps.type_corps == "Etoile" else 0.0025)
    maximum = span_m * (0.028 if corps.type_corps == "Etoile" else 0.012)
    reel = max(corps.rayon_m or 0.0, 0.0)
    return max(minimum, min(maximum, reel))
