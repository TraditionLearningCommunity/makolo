"""Differential-geometry helpers for prescribed four-dimensional metrics."""
from __future__ import annotations

from ..metrics import Coordonnees4, Matrice4, Metrique4D


def inverser_matrice4(matrix: Matrice4) -> Matrice4:
    augmented = [
        [float(matrix[i][j]) for j in range(4)] + [1.0 if i == j else 0.0 for j in range(4)]
        for i in range(4)
    ]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < 1e-30:
            raise ValueError("Metric tensor is singular or numerically non-invertible")
        if pivot != col:
            augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        scale = augmented[col][col]
        augmented[col] = [value / scale for value in augmented[col]]
        for row in range(4):
            if row == col:
                continue
            factor = augmented[row][col]
            if factor != 0.0:
                augmented[row] = [
                    augmented[row][j] - factor * augmented[col][j]
                    for j in range(8)
                ]
    return tuple(tuple(augmented[i][j + 4] for j in range(4)) for i in range(4))


def _pas_derivation(value: float, relatif: float, absolu: float) -> float:
    return max(absolu, abs(value) * relatif)


def derivees_metrique(
    metrique: Metrique4D,
    x: Coordonnees4,
    pas_relatif: float = 1e-5,
    pas_absolu_m: float = 1e-3,
) -> tuple[Matrice4, Matrice4, Matrice4, Matrice4]:
    if pas_relatif <= 0 or pas_absolu_m <= 0:
        raise ValueError("Metric differentiation steps must be positive")
    derivatives = []
    for alpha in range(4):
        h = _pas_derivation(x[alpha], pas_relatif, pas_absolu_m)
        xp = list(x)
        xm = list(x)
        xp[alpha] += h
        xm[alpha] -= h
        gp = metrique.tenseur(tuple(xp))
        gm = metrique.tenseur(tuple(xm))
        derivatives.append(
            tuple(
                tuple((gp[mu][nu] - gm[mu][nu]) / (2.0 * h) for nu in range(4))
                for mu in range(4)
            )
        )
    return tuple(derivatives)  # type: ignore[return-value]


def symboles_christoffel(
    metrique: Metrique4D,
    x: Coordonnees4,
    pas_relatif: float = 1e-5,
    pas_absolu_m: float = 1e-3,
) -> tuple[tuple[tuple[float, ...], ...], ...]:
    g = metrique.tenseur(x)
    inverse = inverser_matrice4(g)
    dg = derivees_metrique(metrique, x, pas_relatif, pas_absolu_m)
    gamma = []
    for mu in range(4):
        by_alpha = []
        for alpha in range(4):
            by_beta = []
            for beta in range(4):
                value = 0.0
                for nu in range(4):
                    value += 0.5 * inverse[mu][nu] * (
                        dg[alpha][nu][beta]
                        + dg[beta][nu][alpha]
                        - dg[nu][alpha][beta]
                    )
                by_beta.append(value)
            by_alpha.append(tuple(by_beta))
        gamma.append(tuple(by_alpha))
    return tuple(gamma)
