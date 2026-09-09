"""Prescribed space-time metrics used by the geodesic layer.

Coordinates in the Cartesian metrics are ``(ct, x, y, z)`` in metres. This
module deliberately provides prescribed geometries; it does not solve the
Einstein field equations for a dynamically evolving metric.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import pi, sqrt
from typing import Callable

from .constants import C, EPSILON_0, G

Coordonnees4 = tuple[float, float, float, float]
Matrice4 = tuple[tuple[float, float, float, float], ...]


def _minkowski() -> Matrice4:
    return (
        (-1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


class Metrique4D(ABC):
    nom: str
    domaine_validite: str
    coordonnees: str

    @abstractmethod
    def tenseur(self, x: Coordonnees4) -> Matrice4:
        raise NotImplementedError

    def contracter(self, x: Coordonnees4, a: Coordonnees4, b: Coordonnees4) -> float:
        g = self.tenseur(x)
        return sum(g[mu][nu] * a[mu] * b[nu] for mu in range(4) for nu in range(4))


@dataclass(frozen=True, slots=True)
class MetriqueMinkowski(Metrique4D):
    nom: str = "Minkowski"
    domaine_validite: str = "flat space-time"
    coordonnees: str = "Cartesian Kerr-Schild-compatible (ct,x,y,z)"

    def tenseur(self, x: Coordonnees4) -> Matrice4:
        return _minkowski()


@dataclass(frozen=True, slots=True)
class MetriqueSchwarzschildKerrSchild(Metrique4D):
    masse_kg: float
    entrant: bool = True
    nom: str = "Schwarzschild Kerr-Schild"
    domaine_validite: str = "isolated spherical non-rotating uncharged source"
    coordonnees: str = "Cartesian Kerr-Schild (ct,x,y,z)"

    def __post_init__(self) -> None:
        if self.masse_kg <= 0:
            raise ValueError("Positive source mass required")

    @property
    def rayon_schwarzschild_m(self) -> float:
        return 2.0 * G * self.masse_kg / (C * C)

    def tenseur(self, x: Coordonnees4) -> Matrice4:
        _, px, py, pz = x
        r = sqrt(px * px + py * py + pz * pz)
        if r == 0:
            raise ValueError("Schwarzschild curvature singularity at r=0")
        h = G * self.masse_kg / (C * C * r)
        sign = 1.0 if self.entrant else -1.0
        k = (1.0, sign * px / r, sign * py / r, sign * pz / r)
        eta = _minkowski()
        return tuple(
            tuple(eta[mu][nu] + 2.0 * h * k[mu] * k[nu] for nu in range(4))
            for mu in range(4)
        )


@dataclass(frozen=True, slots=True)
class MetriqueKerrKerrSchild(Metrique4D):
    masse_kg: float
    spin_dimensionnel: float
    nom: str = "Kerr Kerr-Schild"
    domaine_validite: str = "isolated rotating uncharged black hole, |chi| <= 1"
    coordonnees: str = "Cartesian Kerr-Schild (ct,x,y,z)"

    def __post_init__(self) -> None:
        if self.masse_kg <= 0:
            raise ValueError("Positive source mass required")
        if abs(self.spin_dimensionnel) > 1.0:
            raise ValueError("Kerr black-hole dimensionless spin must satisfy |chi| <= 1")

    @property
    def rayon_gravitationnel_m(self) -> float:
        return G * self.masse_kg / (C * C)

    @property
    def a_m(self) -> float:
        return self.spin_dimensionnel * self.rayon_gravitationnel_m

    @property
    def rayon_horizon_externe_m(self) -> float:
        rg = self.rayon_gravitationnel_m
        return rg * (1.0 + sqrt(1.0 - self.spin_dimensionnel * self.spin_dimensionnel))

    @property
    def rayon_horizon_interne_m(self) -> float:
        rg = self.rayon_gravitationnel_m
        return rg * (1.0 - sqrt(1.0 - self.spin_dimensionnel * self.spin_dimensionnel))

    def rayon_boyer_lindquist(self, x: Coordonnees4) -> float:
        _, px, py, pz = x
        a2 = self.a_m * self.a_m
        rho2 = px * px + py * py + pz * pz
        term = rho2 - a2
        r2 = 0.5 * (term + sqrt(term * term + 4.0 * a2 * pz * pz))
        return sqrt(max(0.0, r2))

    def rayon_ergosphere_externe_m(self, theta_rad: float) -> float:
        from math import cos

        rg = self.rayon_gravitationnel_m
        chi = self.spin_dimensionnel
        return rg * (1.0 + sqrt(1.0 - chi * chi * cos(theta_rad) ** 2))

    def tenseur(self, x: Coordonnees4) -> Matrice4:
        _, px, py, pz = x
        r = self.rayon_boyer_lindquist(x)
        if r == 0:
            raise ValueError("Kerr ring singularity / degenerate r=0 coordinate")
        a = self.a_m
        denom = r * r + a * a
        l = (
            1.0,
            (r * px + a * py) / denom,
            (r * py - a * px) / denom,
            pz / r,
        )
        h = self.rayon_gravitationnel_m * r**3 / (r**4 + a * a * pz * pz)
        eta = _minkowski()
        return tuple(
            tuple(eta[mu][nu] + 2.0 * h * l[mu] * l[nu] for nu in range(4))
            for mu in range(4)
        )


@dataclass(frozen=True, slots=True)
class MetriqueKerrNewmanKerrSchild(Metrique4D):
    """Kerr-Newman black hole in Cartesian Kerr-Schild coordinates.

    ``spin_dimensionnel`` is chi=a/(GM/c²). ``charge_c`` is the SI electric
    charge. The metric depends on Q², while the sign of charge remains relevant
    to electromagnetic interactions outside this purely geometric object.
    """

    masse_kg: float
    spin_dimensionnel: float
    charge_c: float
    nom: str = "Kerr-Newman Kerr-Schild"
    domaine_validite: str = "isolated stationary rotating electrically charged black hole"
    coordonnees: str = "Cartesian Kerr-Schild (ct,x,y,z)"

    def __post_init__(self) -> None:
        if self.masse_kg <= 0:
            raise ValueError("Positive source mass required")
        if abs(self.spin_dimensionnel) > 1.0:
            raise ValueError("Dimensionless spin must satisfy |chi| <= 1 before charge extremality is checked")
        if self.discriminant_horizon_m2 < -1e-18 * self.rayon_gravitationnel_m**2:
            raise ValueError("Kerr-Newman parameters are over-extremal and do not describe a black hole")

    @property
    def rayon_gravitationnel_m(self) -> float:
        return G * self.masse_kg / (C * C)

    @property
    def a_m(self) -> float:
        return self.spin_dimensionnel * self.rayon_gravitationnel_m

    @property
    def charge_geometrique2_m2(self) -> float:
        return G * self.charge_c * self.charge_c / (4.0 * pi * EPSILON_0 * C**4)

    @property
    def discriminant_horizon_m2(self) -> float:
        rg = self.rayon_gravitationnel_m
        return rg * rg - self.a_m * self.a_m - self.charge_geometrique2_m2

    @property
    def rayon_horizon_externe_m(self) -> float:
        return self.rayon_gravitationnel_m + sqrt(max(0.0, self.discriminant_horizon_m2))

    @property
    def rayon_horizon_interne_m(self) -> float:
        return self.rayon_gravitationnel_m - sqrt(max(0.0, self.discriminant_horizon_m2))

    def rayon_boyer_lindquist(self, x: Coordonnees4) -> float:
        _, px, py, pz = x
        a2 = self.a_m * self.a_m
        rho2 = px * px + py * py + pz * pz
        term = rho2 - a2
        r2 = 0.5 * (term + sqrt(term * term + 4.0 * a2 * pz * pz))
        return sqrt(max(0.0, r2))

    def tenseur(self, x: Coordonnees4) -> Matrice4:
        _, px, py, pz = x
        r = self.rayon_boyer_lindquist(x)
        if r == 0:
            raise ValueError("Kerr-Newman ring singularity / degenerate r=0 coordinate")
        a = self.a_m
        denom_l = r * r + a * a
        l = (
            1.0,
            (r * px + a * py) / denom_l,
            (r * py - a * px) / denom_l,
            pz / r,
        )
        denominator = r**4 + a * a * pz * pz
        q2 = self.charge_geometrique2_m2
        h = (self.rayon_gravitationnel_m * r**3 - 0.5 * q2 * r * r) / denominator
        eta = _minkowski()
        return tuple(
            tuple(eta[mu][nu] + 2.0 * h * l[mu] * l[nu] for nu in range(4))
            for mu in range(4)
        )


@dataclass(frozen=True, slots=True)
class MetriqueFLRWPlate(Metrique4D):
    facteur_echelle: Callable[[float], float]
    nom: str = "FLRW spatialement plate"
    domaine_validite: str = "homogeneous isotropic k=0 cosmology with prescribed scale factor"
    coordonnees: str = "comoving Cartesian (ct,x,y,z)"

    def tenseur(self, x: Coordonnees4) -> Matrice4:
        t_s = x[0] / C
        a = float(self.facteur_echelle(t_s))
        if a <= 0:
            raise ValueError("FLRW scale factor must be positive")
        a2 = a * a
        return (
            (-1.0, 0.0, 0.0, 0.0),
            (0.0, a2, 0.0, 0.0),
            (0.0, 0.0, a2, 0.0),
            (0.0, 0.0, 0.0, a2),
        )
