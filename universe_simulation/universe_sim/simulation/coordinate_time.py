"""Synchronize affine-parameter worldline integrators to coordinate time."""
from __future__ import annotations

from typing import Protocol

from ..constants import C
from .geodesic_integrator import EtatGeodesique


class IntegrateurAffine(Protocol):
    def avancer(self, etat: EtatGeodesique, dlambda_m: float) -> None: ...


def _installer(cible: EtatGeodesique, source: EtatGeodesique) -> None:
    cible.coordonnees_m = source.coordonnees_m
    cible.tangente = source.tangente
    cible.parametre_affine_m = source.parametre_affine_m
    cible.type_geodesique = source.type_geodesique


def avancer_jusqua_temps_coordonne(
    integrateur: IntegrateurAffine,
    etat: EtatGeodesique,
    dt_coordonne_s: float,
    *,
    dlambda_max_m: float | None = None,
    tolerance_t_s: float = 1e-12,
    max_sous_pas: int = 10000,
    iterations_bisection: int = 50,
) -> float:
    """Advance a future-directed worldline by an exact coordinate-time step.

    Returns the affine-parameter increment actually consumed. The routine uses
    ``d(ct)/dlambda = u^0`` as the local step estimate and bisects only when a
    trial affine step overshoots the target coordinate time. ``dlambda_max_m``
    can enforce smaller GR integration steps in strong curvature.
    """
    if dt_coordonne_s <= 0:
        raise ValueError("Coordinate-time step must be positive")
    if dlambda_max_m is not None and dlambda_max_m <= 0:
        raise ValueError("Maximum affine step must be positive")
    if tolerance_t_s <= 0 or max_sous_pas <= 0 or iterations_bisection <= 0:
        raise ValueError("Synchronization tolerances and iteration limits must be positive")

    start_lambda = etat.parametre_affine_m
    target_ct = etat.coordonnees_m[0] + C * dt_coordonne_s
    tolerance_ct = C * tolerance_t_s

    for _ in range(max_sous_pas):
        remaining = target_ct - etat.coordonnees_m[0]
        if abs(remaining) <= tolerance_ct:
            return etat.parametre_affine_m - start_lambda
        if remaining < 0:
            raise ArithmeticError("Worldline passed the coordinate-time target without bracketing")
        u0 = etat.tangente[0]
        if u0 <= 0:
            raise ValueError("Coordinate-time synchronization requires a future-directed tangent with u0 > 0")

        trial_dlambda = remaining / u0
        if dlambda_max_m is not None:
            trial_dlambda = min(trial_dlambda, dlambda_max_m)
        before = etat.copier()
        integrateur.avancer(etat, trial_dlambda)
        if etat.coordonnees_m[0] < before.coordonnees_m[0]:
            _installer(etat, before)
            raise ArithmeticError("Coordinate time is not monotonic along the requested future-directed step")

        if etat.coordonnees_m[0] <= target_ct + tolerance_ct:
            continue

        low = 0.0
        high = trial_dlambda
        best = before
        for _ in range(iterations_bisection):
            mid = 0.5 * (low + high)
            candidate = before.copier()
            integrateur.avancer(candidate, mid)
            error = candidate.coordonnees_m[0] - target_ct
            if abs(error) <= tolerance_ct:
                _installer(etat, candidate)
                return etat.parametre_affine_m - start_lambda
            if error < 0:
                low = mid
                best = candidate
            else:
                high = mid
        final_candidate = before.copier()
        integrateur.avancer(final_candidate, high)
        if abs(final_candidate.coordonnees_m[0] - target_ct) < abs(best.coordonnees_m[0] - target_ct):
            best = final_candidate
        _installer(etat, best)
        if abs(etat.coordonnees_m[0] - target_ct) <= 10.0 * tolerance_ct:
            return etat.parametre_affine_m - start_lambda
        raise RuntimeError("Coordinate-time bisection failed to reach requested tolerance")

    raise RuntimeError("Coordinate-time synchronization exceeded maximum substeps")
