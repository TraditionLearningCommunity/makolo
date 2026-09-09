"""Geodesic integration for prescribed space-time metrics."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import sqrt

from ..metrics import Coordonnees4, Metrique4D
from ..services.differential_geometry import symboles_christoffel


class TypeGeodesique(str, Enum):
    TEMPORELLE = "temporelle"
    NULLE = "nulle"


@dataclass(slots=True)
class EtatGeodesique:
    """Coordinate state parameterized by an affine length ``lambda``.

    Coordinates use the convention required by the selected metric. For the
    provided Cartesian metrics this is ``(ct,x,y,z)`` in metres. ``tangente``
    stores ``dx^mu / d lambda``.
    """

    coordonnees_m: Coordonnees4
    tangente: Coordonnees4
    parametre_affine_m: float = 0.0
    type_geodesique: TypeGeodesique = TypeGeodesique.TEMPORELLE

    def norme(self, metrique: Metrique4D) -> float:
        return metrique.contracter(self.coordonnees_m, self.tangente, self.tangente)


@dataclass(slots=True)
class IntegrateurGeodesiqueRK4:
    metrique: Metrique4D
    pas_relatif_derivation: float = 1e-5
    pas_absolu_derivation_m: float = 1e-3
    nom: str = "Runge-Kutta 4 geodesique"

    def _derivee(self, y: tuple[float, ...]) -> tuple[float, ...]:
        x = tuple(y[:4])
        u = tuple(y[4:])
        gamma = symboles_christoffel(
            self.metrique,
            x,  # type: ignore[arg-type]
            self.pas_relatif_derivation,
            self.pas_absolu_derivation_m,
        )
        du = []
        for mu in range(4):
            value = 0.0
            for alpha in range(4):
                for beta in range(4):
                    value -= gamma[mu][alpha][beta] * u[alpha] * u[beta]
            du.append(value)
        return tuple(u) + tuple(du)

    @staticmethod
    def _ajouter(y: tuple[float, ...], k: tuple[float, ...], facteur: float) -> tuple[float, ...]:
        return tuple(y[i] + facteur * k[i] for i in range(8))

    def avancer(self, etat: EtatGeodesique, dlambda_m: float) -> None:
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


def construire_tangente_normalisee(
    metrique: Metrique4D,
    coordonnees_m: Coordonnees4,
    tangente_spatiale: tuple[float, float, float],
    type_geodesique: TypeGeodesique = TypeGeodesique.TEMPORELLE,
    future: bool = True,
) -> Coordonnees4:
    """Complete a spatial tangent with the causal time component.

    Timelike tangents are normalized to ``g(u,u)=-1`` so the affine parameter
    is proper length ``c*d tau``. Null tangents satisfy ``g(k,k)=0``.
    """
    g = metrique.tenseur(coordonnees_m)
    spatial = tuple(float(v) for v in tangente_spatiale)
    target = -1.0 if type_geodesique == TypeGeodesique.TEMPORELLE else 0.0
    a = g[0][0]
    b = 2.0 * sum(g[0][i + 1] * spatial[i] for i in range(3))
    c_term = sum(
        g[i + 1][j + 1] * spatial[i] * spatial[j]
        for i in range(3)
        for j in range(3)
    ) - target
    if abs(a) < 1e-15:
        if abs(b) < 1e-15:
            raise ValueError("Cannot determine temporal tangent component in this coordinate chart")
        roots = (-c_term / b,)
    else:
        discriminant = b * b - 4.0 * a * c_term
        if discriminant < -1e-12:
            raise ValueError("Requested spatial tangent has no real causal completion")
        root = sqrt(max(0.0, discriminant))
        roots = ((-b + root) / (2.0 * a), (-b - root) / (2.0 * a))
    candidates = [value for value in roots if (value > 0 if future else value < 0)]
    if not candidates:
        raise ValueError("No tangent root matches the requested time orientation")
    u0 = max(candidates) if future else min(candidates)
    return (u0, spatial[0], spatial[1], spatial[2])
