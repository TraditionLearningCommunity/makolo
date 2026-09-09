"""Geodesic integration for prescribed space-time metrics."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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
