"""Forced timelike worldline integration in a prescribed space-time metric."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..constants import C
from ..metrics import Coordonnees4, Metrique4D
from ..services.differential_geometry import symboles_christoffel
from .geodesic_integrator import EtatGeodesique, TypeGeodesique

QuadraccelerationProvider = Callable[[Coordonnees4, Coordonnees4], Coordonnees4]


@dataclass(slots=True)
class IntegrateurLigneUniversForceeRK4:
    """Integrate a massive accelerated worldline with ``lambda = c*tau``.

    The provider returns physical four-acceleration ``A^mu`` in m/s². The
    equation integrated is

    ``du^mu/dlambda = -Gamma^mu_ab u^a u^b + A^mu/c²``.

    A physically valid massive-particle provider should satisfy ``g(u,A)=0``.
    This path is therefore distinct both from a free geodesic and from the
    Newtonian ``F/m`` engine.
    """

    metrique: Metrique4D
    quadracceleration: QuadraccelerationProvider
    pas_relatif_derivation: float = 1e-5
    pas_absolu_derivation_m: float = 1e-3
    verifier_orthogonalite: bool = True
    tolerance_orthogonalite: float = 1e-8
    nom: str = "Runge-Kutta 4 ligne d'univers forcee"

    def _derivee(self, y: tuple[float, ...]) -> tuple[float, ...]:
        x = tuple(y[:4])
        u = tuple(y[4:])
        gamma = symboles_christoffel(
            self.metrique,
            x,  # type: ignore[arg-type]
            self.pas_relatif_derivation,
            self.pas_absolu_derivation_m,
        )
        acceleration = self.quadracceleration(x, u)  # type: ignore[arg-type]
        if self.verifier_orthogonalite:
            contraction = self.metrique.contracter(x, u, acceleration)  # type: ignore[arg-type]
            scale = max(1.0, sum(abs(value) for value in acceleration))
            if abs(contraction) > self.tolerance_orthogonalite * scale:
                raise ValueError("Four-acceleration must be orthogonal to the timelike four-velocity")
        du = []
        for mu in range(4):
            value = acceleration[mu] / (C * C)
            for alpha in range(4):
                for beta in range(4):
                    value -= gamma[mu][alpha][beta] * u[alpha] * u[beta]
            du.append(value)
        return tuple(u) + tuple(du)

    @staticmethod
    def _ajouter(y: tuple[float, ...], k: tuple[float, ...], facteur: float) -> tuple[float, ...]:
        return tuple(y[i] + facteur * k[i] for i in range(8))

    def avancer(self, etat: EtatGeodesique, dlambda_m: float) -> None:
        if etat.type_geodesique != TypeGeodesique.TEMPORELLE:
            raise ValueError("Proper acceleration applies to massive timelike worldlines")
        if dlambda_m == 0:
            return
        y0 = tuple(etat.coordonnees_m) + tuple(etat.tangente)
        k1 = self._derivee(y0)
        k2 = self._derivee(self._ajouter(y0, k1, 0.5 * dlambda_m))
        k3 = self._derivee(self._ajouter(y0, k2, 0.5 * dlambda_m))
        k4 = self._derivee(self._ajouter(y0, k3, dlambda_m))
        y1 = tuple(
            y0[i] + dlambda_m * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]) / 6.0
            for i in range(8)
        )
        etat.coordonnees_m = tuple(y1[:4])  # type: ignore[assignment]
        etat.tangente = tuple(y1[4:])  # type: ignore[assignment]
        etat.parametre_affine_m += dlambda_m
