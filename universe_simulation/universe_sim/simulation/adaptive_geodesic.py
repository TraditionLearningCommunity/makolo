"""Adaptive geodesic integration by RK4 step doubling."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..metrics import Metrique4D
from .geodesic_integrator import EtatGeodesique, IntegrateurGeodesiqueRK4


def _state_vector(state: EtatGeodesique) -> tuple[float, ...]:
    return tuple(state.coordonnees_m) + tuple(state.tangente)


def _install(target: EtatGeodesique, source: EtatGeodesique) -> None:
    target.coordonnees_m = source.coordonnees_m
    target.tangente = source.tangente
    target.parametre_affine_m = source.parametre_affine_m
    target.type_geodesique = source.type_geodesique


@dataclass(slots=True)
class IntegrateurGeodesiqueAdaptatif:
    """Adaptive wrapper around the existing RK4 geodesic integrator.

    One full RK4 step is compared with two half steps. The two-half-step result
    is accepted when the scaled local discrepancy is below one; otherwise the
    requested affine interval is recursively subdivided. The algorithm never
    changes the physical metric or re-normalizes a trajectory by force.
    """

    metrique: Metrique4D
    tolerance_relative: float = 1e-9
    tolerance_absolue: float = 1e-6
    max_subdivisions: int = 20
    pas_relatif_derivation: float = 1e-5
    pas_absolu_derivation_m: float = 1e-3
    nom: str = "RK4 geodesique adaptatif par step-doubling"
    dernier_nombre_sous_pas: int = field(default=0, init=False)
    derniere_erreur_normalisee: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if self.tolerance_relative <= 0 or self.tolerance_absolue <= 0:
            raise ValueError("Adaptive geodesic tolerances must be positive")
        if self.max_subdivisions < 0:
            raise ValueError("Maximum subdivisions cannot be negative")

    def _rk4(self) -> IntegrateurGeodesiqueRK4:
        return IntegrateurGeodesiqueRK4(
            self.metrique,
            self.pas_relatif_derivation,
            self.pas_absolu_derivation_m,
        )

    def _erreur(self, full: EtatGeodesique, half: EtatGeodesique) -> float:
        yf = _state_vector(full)
        yh = _state_vector(half)
        errors = []
        for a, b in zip(yf, yh):
            scale = self.tolerance_absolue + self.tolerance_relative * max(1.0, abs(a), abs(b))
            errors.append(abs(a - b) / scale)
        return max(errors)

    def _avancer_intervalle(self, state: EtatGeodesique, dlambda_m: float, depth: int) -> None:
        base = state.copier()
        full = base.copier()
        self._rk4().avancer(full, dlambda_m)

        half = base.copier()
        solver = self._rk4()
        solver.avancer(half, 0.5 * dlambda_m)
        solver.avancer(half, 0.5 * dlambda_m)
        error = self._erreur(full, half)
        self.derniere_erreur_normalisee = max(self.derniere_erreur_normalisee, error)

        if error <= 1.0:
            _install(state, half)
            self.dernier_nombre_sous_pas += 2
            return
        if depth >= self.max_subdivisions:
            raise RuntimeError(
                f"Adaptive geodesic integration failed requested tolerance after {depth} subdivisions; "
                f"normalized error={error:.6g}"
            )
        self._avancer_intervalle(state, 0.5 * dlambda_m, depth + 1)
        self._avancer_intervalle(state, 0.5 * dlambda_m, depth + 1)

    def avancer(self, etat: EtatGeodesique, dlambda_m: float) -> None:
        if dlambda_m == 0:
            return
        self.dernier_nombre_sous_pas = 0
        self.derniere_erreur_normalisee = 0.0
        self._avancer_intervalle(etat, dlambda_m, 0)
