"""Local orthonormal observer frames for measurements in curved space-time."""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from ..constants import C
from ..metrics import Coordonnees4, Metrique4D

Tangent4 = Coordonnees4


def _add(a: Tangent4, b: Tangent4) -> Tangent4:
    return tuple(a[i] + b[i] for i in range(4))  # type: ignore[return-value]


def _scale(a: Tangent4, factor: float) -> Tangent4:
    return tuple(factor * a[i] for i in range(4))  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class TetradeLocale:
    """Orthonormal tetrad ``e_(a)^mu`` carried by a local observer.

    ``temps`` is the observer's future-directed normalized four-velocity. The
    three spatial vectors span the observer's instantaneous rest space.
    """

    temps: Tangent4
    espace_1: Tangent4
    espace_2: Tangent4
    espace_3: Tangent4

    @property
    def base(self) -> tuple[Tangent4, Tangent4, Tangent4, Tangent4]:
        return self.temps, self.espace_1, self.espace_2, self.espace_3

    def verifier(self, metrique: Metrique4D, x: Coordonnees4, tolerance: float = 1e-9) -> bool:
        eta = (-1.0, 1.0, 1.0, 1.0)
        for a, ea in enumerate(self.base):
            for b, eb in enumerate(self.base):
                target = eta[a] if a == b else 0.0
                if abs(metrique.contracter(x, ea, eb) - target) > tolerance:
                    return False
        return True

    def composantes_locales(self, metrique: Metrique4D, x: Coordonnees4, vecteur: Tangent4) -> Tangent4:
        """Return contravariant components in the local orthonormal frame."""
        temporal = -metrique.contracter(x, self.temps, vecteur)
        spatials = tuple(
            metrique.contracter(x, basis, vecteur)
            for basis in (self.espace_1, self.espace_2, self.espace_3)
        )
        return (temporal, spatials[0], spatials[1], spatials[2])

    def vitesse_locale(self, metrique: Metrique4D, x: Coordonnees4, tangente: Tangent4) -> tuple[float, float, float]:
        """Return locally measured three-velocity in m/s.

        For a timelike normalized tangent this is the physical velocity seen by
        the observer. For a future-directed null tangent its magnitude is c.
        """
        local = self.composantes_locales(metrique, x, tangente)
        if local[0] <= 0:
            raise ValueError("The measured tangent must be future-directed for this observer")
        return (
            C * local[1] / local[0],
            C * local[2] / local[0],
            C * local[3] / local[0],
        )

    def gamma_local(self, metrique: Metrique4D, x: Coordonnees4, tangente_timelike: Tangent4) -> float:
        local = self.composantes_locales(metrique, x, tangente_timelike)
        if local[0] < 1.0 - 1e-9:
            raise ValueError("Expected a future-directed normalized timelike tangent")
        return local[0]


def construire_tetrade_observateur(
    metrique: Metrique4D,
    x: Coordonnees4,
    quadrivitesse_observateur: Tangent4,
    graines_spatiales: tuple[Tangent4, Tangent4, Tangent4] | None = None,
    tolerance: float = 1e-12,
) -> TetradeLocale:
    """Build an observer tetrad with metric Gram-Schmidt orthonormalization."""
    norm = metrique.contracter(x, quadrivitesse_observateur, quadrivitesse_observateur)
    if norm >= 0:
        raise ValueError("Observer four-velocity must be timelike")
    e0 = _scale(quadrivitesse_observateur, 1.0 / sqrt(-norm))
    if e0[0] <= 0:
        e0 = _scale(e0, -1.0)

    seeds = graines_spatiales or (
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    basis: list[Tangent4] = [e0]
    norms: list[float] = [-1.0]
    for seed in seeds:
        work = seed
        for existing, existing_norm in zip(basis, norms):
            coeff = metrique.contracter(x, work, existing) / existing_norm
            work = _add(work, _scale(existing, -coeff))
        work_norm = metrique.contracter(x, work, work)
        if work_norm <= tolerance:
            raise ValueError("Spatial seed vectors cannot form an observer rest-frame tetrad here")
        work = _scale(work, 1.0 / sqrt(work_norm))
        basis.append(work)
        norms.append(1.0)

    tetrad = TetradeLocale(basis[0], basis[1], basis[2], basis[3])
    if not tetrad.verifier(metrique, x, tolerance=max(1e-9, 100.0 * tolerance)):
        raise ArithmeticError("Failed to construct an orthonormal local tetrad")
    return tetrad


def construire_tetrade_observateur_stationnaire(metrique: Metrique4D, x: Coordonnees4) -> TetradeLocale:
    """Construct a coordinate-stationary observer where that worldline is timelike.

    This deliberately fails at/inside regions where the coordinate-stationary
    direction is null or spacelike (for example at and inside a Schwarzschild
    event horizon).
    """
    return construire_tetrade_observateur(metrique, x, (1.0, 0.0, 0.0, 0.0))
