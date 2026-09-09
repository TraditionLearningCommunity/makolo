"""Contiguous state backend for large classical/SR populations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, TYPE_CHECKING

import numpy as np

from ..constants import C
from ..regimes import RegimeDynamique
from ..values import GrandeurPhysique, Vecteur3

if TYPE_CHECKING:
    from ..bodies import CorpsPhysique

_REGIME_TO_CODE = {
    RegimeDynamique.CLASSIQUE: 0,
    RegimeDynamique.RELATIVISTE_SPECIAL: 1,
}
_CODE_TO_REGIME = {value: key for key, value in _REGIME_TO_CODE.items()}


def _array3(vector: Vecteur3) -> np.ndarray:
    return np.asarray((vector.x, vector.y, vector.z), dtype=np.float64)


def _vitesses_sr_depuis_impulsions(momentum: np.ndarray, masses: np.ndarray) -> np.ndarray:
    """Derive float64 SR velocities from canonical momentum robustly.

    Positive rest mass guarantees a timelike momentum state. At enormous
    gamma, the mathematical speed differs from c by less than one float64 ulp
    and may round to exactly c. In that representational corner only, project
    the derived velocity to the greatest representable speed below c while
    leaving the canonical momentum untouched.
    """
    p = np.asarray(momentum, dtype=np.float64)
    m = np.asarray(masses, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 3 or m.shape != (p.shape[0],):
        raise ValueError("SR momentum/mass arrays must have shapes (N,3) and (N,)")
    if np.any(m <= 0):
        raise ValueError("SR rows require positive rest mass")
    if np.any(~np.isfinite(p)) or np.any(~np.isfinite(m)):
        raise ValueError("SR momentum and rest mass must be finite")

    p_norm = np.hypot(np.hypot(np.abs(p[:, 0]), np.abs(p[:, 1])), np.abs(p[:, 2]))
    denominator = np.hypot(m * C, p_norm)
    velocity = p * ((C / denominator)[:, None])

    speed = np.hypot(
        np.hypot(np.abs(velocity[:, 0]), np.abs(velocity[:, 1])),
        np.abs(velocity[:, 2]),
    )
    rounded_to_c = speed >= C
    if np.any(rounded_to_c):
        nonzero = rounded_to_c & (p_norm > 0)
        representable_causal_speed = np.nextafter(C, 0.0)
        velocity[nonzero] = (p[nonzero] / p_norm[nonzero, None]) * representable_causal_speed
        # A multidimensional norm can itself round upward by one ulp. Apply a
        # second representational contraction only if that happens.
        corrected = np.hypot(
            np.hypot(np.abs(velocity[nonzero, 0]), np.abs(velocity[nonzero, 1])),
            np.abs(velocity[nonzero, 2]),
        )
        needs_second = corrected >= C
        if np.any(needs_second):
            rows = np.flatnonzero(nonzero)[needs_second]
            velocity[rows] *= np.nextafter(1.0, 0.0)
    return velocity


@dataclass(slots=True)
class ArrayStateBackend:
    """Structure-of-arrays representation of hot simulation state.

    The physical Python objects remain the identities and semantic model. This
    backend only mirrors classical and flat-space SR kinematics for efficient
    numerical loops. Curved-space-time states are intentionally rejected.
    """

    body_ids: tuple[str, ...]
    positions_m: np.ndarray
    velocities_m_s: np.ndarray
    momenta_kg_m_s: np.ndarray
    masses_kg: np.ndarray
    charges_c: np.ndarray
    proper_times_s: np.ndarray
    active: np.ndarray
    regime_codes: np.ndarray
    _index: dict[str, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._index = {body_id: i for i, body_id in enumerate(self.body_ids)}
        if len(self._index) != len(self.body_ids):
            raise ValueError("Body ids must be unique")
        n = len(self.body_ids)
        expected_2d = (n, 3)
        for name in ("positions_m", "velocities_m_s", "momenta_kg_m_s"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.shape != expected_2d:
                raise ValueError(f"{name} must have shape {expected_2d}")
            setattr(self, name, np.ascontiguousarray(value))
        for name, dtype in (
            ("masses_kg", np.float64),
            ("charges_c", np.float64),
            ("proper_times_s", np.float64),
            ("active", np.bool_),
            ("regime_codes", np.int8),
        ):
            value = np.asarray(getattr(self, name), dtype=dtype)
            if value.shape != (n,):
                raise ValueError(f"{name} must have shape {(n,)}")
            setattr(self, name, np.ascontiguousarray(value))
        if np.any(self.masses_kg < 0):
            raise ValueError("Masses must be non-negative")
        known = np.fromiter(_CODE_TO_REGIME.keys(), dtype=np.int8)
        if np.any(~np.isin(self.regime_codes, known)):
            raise ValueError("Unsupported dynamics regime code in array backend")

    @classmethod
    def depuis_corps(cls, corps: Iterable["CorpsPhysique"]) -> "ArrayStateBackend":
        bodies = tuple(corps)
        n = len(bodies)
        positions = np.zeros((n, 3), dtype=np.float64)
        velocities = np.zeros((n, 3), dtype=np.float64)
        momenta = np.zeros((n, 3), dtype=np.float64)
        masses = np.zeros(n, dtype=np.float64)
        charges = np.zeros(n, dtype=np.float64)
        proper_times = np.full(n, np.nan, dtype=np.float64)
        active = np.zeros(n, dtype=np.bool_)
        regimes = np.zeros(n, dtype=np.int8)

        for i, body in enumerate(bodies):
            state = body.etat()
            if getattr(state, "espace_temps", None) is not None:
                raise ValueError(
                    f"{body.nom} uses curved-space-time kinematics; keep it on the object/GR backend"
                )
            mass_state = getattr(state, "massique", None)
            mass = 0.0 if mass_state is None else float(mass_state.masse.value)
            if mass < 0:
                raise ValueError(f"{body.nom} has negative mass")
            masses[i] = mass
            electric = getattr(state, "electrique", None)
            charges[i] = 0.0 if electric is None else float(electric.charge_nette.value)
            active[i] = bool(body.actif)

            translation = getattr(state, "translation", None)
            relativistic = getattr(state, "relativiste", None)
            if translation is not None:
                positions[i] = _array3(translation.position)
                velocities[i] = _array3(translation.vitesse)
                momenta[i] = mass * velocities[i]
                regimes[i] = _REGIME_TO_CODE[RegimeDynamique.CLASSIQUE]
            elif relativistic is not None:
                if mass <= 0:
                    raise ValueError(f"{body.nom} needs positive rest mass for SR array kinematics")
                positions[i] = _array3(relativistic.position)
                momenta[i] = _array3(relativistic.impulsion)
                velocities[i] = _vitesses_sr_depuis_impulsions(momenta[i : i + 1], masses[i : i + 1])[0]
                proper_times[i] = float(relativistic.temps_propre_s)
                regimes[i] = _REGIME_TO_CODE[RegimeDynamique.RELATIVISTE_SPECIAL]
            else:
                raise ValueError(f"{body.nom} has no supported kinematic state")

        return cls(
            tuple(body.id for body in bodies),
            positions,
            velocities,
            momenta,
            masses,
            charges,
            proper_times,
            active,
            regimes,
        )

    def index(self, body_id: str) -> int:
        try:
            return self._index[body_id]
        except KeyError as exc:
            raise KeyError(f"Unknown body id: {body_id}") from exc

    def regime(self, body_id: str) -> RegimeDynamique:
        return _CODE_TO_REGIME[int(self.regime_codes[self.index(body_id)])]

    def rafraichir_vitesses(self) -> None:
        """Recompute velocities from each regime's canonical momentum."""
        classical = self.regime_codes == _REGIME_TO_CODE[RegimeDynamique.CLASSIQUE]
        positive_classical = classical & (self.masses_kg > 0)
        self.velocities_m_s[positive_classical] = (
            self.momenta_kg_m_s[positive_classical] / self.masses_kg[positive_classical, None]
        )
        zero_mass_classical = classical & (self.masses_kg == 0)
        self.momenta_kg_m_s[zero_mass_classical] = 0.0

        sr = self.regime_codes == _REGIME_TO_CODE[RegimeDynamique.RELATIVISTE_SPECIAL]
        if np.any(sr):
            masses = self.masses_kg[sr]
            if np.any(masses <= 0):
                raise ValueError("SR rows require positive rest mass")
            momenta = self.momenta_kg_m_s[sr]
            self.velocities_m_s[sr] = _vitesses_sr_depuis_impulsions(momenta, masses)

    def synchroniser_vers_corps(self, corps: Iterable["CorpsPhysique"]) -> None:
        bodies = tuple(corps)
        by_id = {body.id: body for body in bodies}
        if set(by_id) != set(self.body_ids):
            raise ValueError("Bodies do not match the array backend registry")
        self.rafraichir_vitesses()
        for i, body_id in enumerate(self.body_ids):
            body = by_id[body_id]
            state = body.etat()
            position = Vecteur3.from_iterable(self.positions_m[i])
            velocity = Vecteur3.from_iterable(self.velocities_m_s[i])
            momentum = Vecteur3.from_iterable(self.momenta_kg_m_s[i])
            regime = _CODE_TO_REGIME[int(self.regime_codes[i])]
            if regime == RegimeDynamique.CLASSIQUE:
                if state.translation is None or state.relativiste is not None or state.espace_temps is not None:
                    raise ValueError(f"{body.nom} no longer matches its classical backend representation")
                state.translation.position = position
                state.translation.vitesse = velocity
            elif regime == RegimeDynamique.RELATIVISTE_SPECIAL:
                if state.relativiste is None or state.translation is not None or state.espace_temps is not None:
                    raise ValueError(f"{body.nom} no longer matches its SR backend representation")
                state.relativiste.position = position
                state.relativiste.impulsion = momentum
                state.relativiste.temps_propre_s = float(self.proper_times_s[i])
            else:  # defensive; __post_init__ already rejects unknown codes
                raise ValueError(f"Unsupported array regime: {regime}")

            if state.massique is not None:
                old = state.massique.masse
                state.massique.masse = GrandeurPhysique(float(self.masses_kg[i]), old.unit, old.uncertainty)
            elif self.masses_kg[i] != 0.0:
                raise ValueError(f"{body.nom} cannot receive non-zero mass without a mass state")
            if state.electrique is not None:
                old_charge = state.electrique.charge_nette
                state.electrique.charge_nette = GrandeurPhysique(
                    float(self.charges_c[i]), old_charge.unit, old_charge.uncertainty
                )
            elif self.charges_c[i] != 0.0:
                raise ValueError(&"{body.nom} cannot receive non-zero charge without an electric state")
            body.actif = bool(self.active[i])

    def copier(self) -> "ArrayStateBackend":
        return ArrayStateBackend(
            self.body_ids,
            self.positions_m.copy(),
            self.velocities_m_s.copy(),
            self.momenta_kg_m_s.copy(),
            self.masses_kg.copy(),
            self.charges_c.copy(),
            self.proper_times_s.copy(),
            self.active.copy(),
            self.regime_codes.copy(),
        )
