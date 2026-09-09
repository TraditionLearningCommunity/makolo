"""Numerical selection of an appropriate dynamics regime.

The thresholds are simulation-accuracy policy, not universal boundaries in
nature. Automatic selection is optional; explicit per-body configuration
remains authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass

from .constants import C
from .regimes import RegimeDynamique
from .values import Vecteur3


@dataclass(frozen=True, slots=True)
class SeuilsSelectionRegime:
    precision_newtonienne: float = 1e-6
    beta_sr_direct: float = 0.1
    potentiel_reduit_champ_fort: float = 1e-2

    def __post_init__(self) -> None:
        if self.precision_newtonienne <= 0:
            raise ValueError("Newtonian target precision must be positive")
        if not 0 < self.beta_sr_direct < 1:
            raise ValueError("Direct-SR beta threshold must lie in (0,1)")
        if not 0 < self.potentiel_reduit_champ_fort < 1:
            raise ValueError("Strong-field reduced-potential threshold must lie in (0,1)")


@dataclass(frozen=True, slots=True)
class DiagnosticRegime:
    regime: RegimeDynamique
    beta: float
    beta2: float
    potentiel_reduit: float
    raison: str


def diagnostiquer_regime(
    vitesse: Vecteur3,
    potentiel_gravitationnel_specifique_j_kg: float = 0.0,
    seuils: SeuilsSelectionRegime | None = None,
    imposer_geodesique: bool = False,
) -> DiagnosticRegime:
    seuils = seuils or SeuilsSelectionRegime()
    beta = vitesse.norm() / C
    if beta >= 1.0:
        raise ValueError("A massive-body regime cannot be selected for |v| >= c")
    beta2 = beta * beta
    potentiel_reduit = abs(potentiel_gravitationnel_specifique_j_kg) / (C * C)

    if imposer_geodesique or potentiel_reduit >= seuils.potentiel_reduit_champ_fort:
        return DiagnosticRegime(
            RegimeDynamique.GEODESIQUE,
            beta,
            beta2,
            potentiel_reduit,
            "strong prescribed curvature or explicitly requested geodesic evolution",
        )

    if beta >= seuils.beta_sr_direct:
        if potentiel_reduit >= seuils.precision_newtonienne:
            return DiagnosticRegime(
                RegimeDynamique.GEODESIQUE,
                beta,
                beta2,
                potentiel_reduit,
                "relativistic speed with gravitational curvature above the requested error budget",
            )
        return DiagnosticRegime(
            RegimeDynamique.RELATIVISTE_SPECIAL,
            beta,
            beta2,
            potentiel_reduit,
            "relativistic speed while gravity is negligible at the requested accuracy",
        )

    if max(beta2, potentiel_reduit) >= seuils.precision_newtonienne:
        return DiagnosticRegime(
            RegimeDynamique.POST_NEWTONIEN_1PN,
            beta,
            beta2,
            potentiel_reduit,
            "relativistic correction exceeds requested Newtonian error budget",
        )

    return DiagnosticRegime(
        RegimeDynamique.CLASSIQUE,
        beta,
        beta2,
        potentiel_reduit,
        "Newtonian corrections remain below requested error budget",
    )
