"""Lorentz transformations in flat space-time.

The boost velocity is the velocity of the target inertial frame with respect
to the source frame. Curved-space-time coordinate changes belong to the GR
metric/geodesic layer, not here.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..constants import C
from ..relativistic_values import Quadrimpulsion, Quadrivecteur, facteur_lorentz
from ..values import Vecteur3


@dataclass(frozen=True, slots=True)
class EvenementMinkowski:
    t_s: float
    position_m: Vecteur3

    def intervalle_depuis(self, autre: "EvenementMinkowski") -> float:
        dt = self.t_s - autre.t_s
        dr = self.position_m - autre.position_m
        return -(C * dt) ** 2 + dr.norm2()


def transformer_evenement_lorentz(evenement: EvenementMinkowski, vitesse_cible: Vecteur3) -> EvenementMinkowski:
    u2 = vitesse_cible.norm2()
    if u2 == 0:
        return evenement
    gamma = facteur_lorentz(vitesse_cible)
    dot = vitesse_cible.dot(evenement.position_m)
    t_prime = gamma * (evenement.t_s - dot / (C * C))
    position_prime = evenement.position_m + vitesse_cible * (
        ((gamma - 1.0) * dot / u2) - gamma * evenement.t_s
    )
    return EvenementMinkowski(t_prime, position_prime)


def transformer_vitesse_lorentz(vitesse_objet: Vecteur3, vitesse_cible: Vecteur3) -> Vecteur3:
    u2 = vitesse_cible.norm2()
    if u2 == 0:
        return vitesse_objet
    gamma_u = facteur_lorentz(vitesse_cible)
    denom = 1.0 - vitesse_cible.dot(vitesse_objet) / (C * C)
    if denom <= 0:
        raise ValueError("Lorentz velocity transform has a non-positive denominator")
    projection = vitesse_objet.dot(vitesse_cible) / u2
    v_parallel = vitesse_cible * projection
    v_perp = vitesse_objet - v_parallel
    transformed_parallel = (v_parallel - vitesse_cible) / denom
    transformed_perp = v_perp / (gamma_u * denom)
    result = transformed_parallel + transformed_perp
    if result.norm() >= C * (1.0 + 1e-12):
        raise ArithmeticError("Lorentz transform produced a superluminal velocity")
    return result


def transformer_quadrivecteur_lorentz(quadrivecteur: Quadrivecteur, vitesse_cible: Vecteur3) -> Quadrivecteur:
    u2 = vitesse_cible.norm2()
    if u2 == 0:
        return quadrivecteur
    gamma = facteur_lorentz(vitesse_cible)
    dot = vitesse_cible.dot(quadrivecteur.spatial)
    temporal = gamma * (quadrivecteur.temporel - dot / C)
    spatial = quadrivecteur.spatial + vitesse_cible * (
        ((gamma - 1.0) * dot / u2) - gamma * quadrivecteur.temporel / C
    )
    return Quadrivecteur(temporal, spatial)


def transformer_quadrimpulsion_lorentz(
    quadrimpulsion: Quadrimpulsion,
    vitesse_cible: Vecteur3,
) -> Quadrimpulsion:
    transformed = transformer_quadrivecteur_lorentz(
        Quadrivecteur(quadrimpulsion.energie_sur_c, quadrimpulsion.impulsion),
        vitesse_cible,
    )
    return Quadrimpulsion(transformed.temporel, transformed.spatial)


def transformation_inverse_evenement(evenement: EvenementMinkowski, vitesse_cible: Vecteur3) -> EvenementMinkowski:
    return transformer_evenement_lorentz(evenement, -vitesse_cible)
