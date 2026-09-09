"""Relativistic frequency and redshift observables."""
from __future__ import annotations

from math import sqrt

from ..metrics import Coordonnees4, Metrique4D


def frequence_photon_mesuree_relative(
    metrique: Metrique4D,
    coordonnees: Coordonnees4,
    tangente_photon: Coordonnees4,
    quadrivitesse_observateur: Coordonnees4,
) -> float:
    """Return observed photon frequency up to the photon's affine scale.

    With signature ``-+++``, an observer measures ``omega = -g(u,k)``. The
    absolute normalization of ``k`` depends on the chosen affine parameter, but
    frequency ratios along the same ray are physical.
    """
    omega = -metrique.contracter(coordonnees, quadrivitesse_observateur, tangente_photon)
    if omega <= 0:
        raise ValueError("Future-directed observer and photon must give positive measured frequency")
    return omega


def rapport_frequences_photon(
    metrique_emission: Metrique4D,
    coordonnees_emission: Coordonnees4,
    tangente_emission: Coordonnees4,
    observateur_emission: Coordonnees4,
    metrique_reception: Metrique4D,
    coordonnees_reception: Coordonnees4,
    tangente_reception: Coordonnees4,
    observateur_reception: Coordonnees4,
) -> float:
    emitted = frequence_photon_mesuree_relative(
        metrique_emission,
        coordonnees_emission,
        tangente_emission,
        observateur_emission,
    )
    received = frequence_photon_mesuree_relative(
        metrique_reception,
        coordonnees_reception,
        tangente_reception,
        observateur_reception,
    )
    return received / emitted


def decalage_vers_rouge_depuis_rapport(rapport_frequence_recue_sur_emise: float) -> float:
    if rapport_frequence_recue_sur_emise <= 0:
        raise ValueError("Frequency ratio must be positive")
    return 1.0 / rapport_frequence_recue_sur_emise - 1.0


def facteur_doppler_longitudinal_sr(beta_recession: float) -> float:
    """Observed/emitted frequency ratio for collinear SR recession."""
    if abs(beta_recession) >= 1:
        raise ValueError("Longitudinal Doppler beta must satisfy |beta| < 1")
    return sqrt((1.0 - beta_recession) / (1.0 + beta_recession))


def decalage_cosmologique_flrw(facteur_echelle_emission: float, facteur_echelle_reception: float) -> float:
    if facteur_echelle_emission <= 0 or facteur_echelle_reception <= 0:
        raise ValueError("FLRW scale factors must be positive")
    return facteur_echelle_reception / facteur_echelle_emission - 1.0
