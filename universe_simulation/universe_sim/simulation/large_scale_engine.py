"""Hot array-backed orchestration for large multi-regime simulations.

This module deliberately keeps the numerical backends authoritative between
explicit synchronization barriers. It avoids the O(N) cost of copying array
state back into every Python physical object after every numerical step.

Cross-regime coupling is never implicit: force/field providers must be attached
explicitly to the population domain that needs them. This prevents a
special-relativistic population from accidentally being evolved with a
Newtonian ``F/m -> dv/dt`` rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

import numpy as np

from ..events import EvenementPhysique
from ..regimes import RegimeDynamique
from ..systems import Univers
from ..values import Instant
from .array_backend import ArrayStateBackend
from .population import IntegrateurPopulationNewtonienneTableau
from .sr_population import IntegrateurPopulationSRTableau


ForceProviderSRHot = Callable[[ArrayStateBackend, Instant], np.ndarray]


def _forces_sr_nulles(backend: ArrayStateBackend, _instant: Instant) -> np.ndarray:
    return np.zeros_like(backend.momenta_kg_m_s)


class DomaineEvolutionGrandeEchelle(Protocol):
    nom: str
    regime: RegimeDynamique

    @property
    def corps_ids(self) -> tuple[str, ...]: ...

    def avancer_hot(self, instant: Instant, dt_s: float) -> list[EvenementPhysique]: ...

    def synchroniser_objets(self, univers: Univers, instant: Instant) -> None: ...


@dataclass(slots=True)
class DomainePopulationClassique:
    """Large classical population whose array backend is authoritative."""

    nom: str
    backend: ArrayStateBackend
    integrateur: IntegrateurPopulationNewtonienneTableau = field(
        default_factory=IntegrateurPopulationNewtonienneTableau
    )
    regime: RegimeDynamique = field(default=RegimeDynamique.CLASSIQUE, init=False)

    def __post_init__(self) -> None:
        classical = np.zeros(len(self.backend.body_ids), dtype=np.int8)
        if not np.array_equal(self.backend.regime_codes, classical):
            raise ValueError("Classical hot domain accepts only classical array rows")

    @property
    def corps_ids(self) -> tuple[str, ...]:
        return self.backend.body_ids

    def avancer_hot(self, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        self.integrateur.avancer(self.backend, dt_s)
        return []

    def synchroniser_objets(self, univers: Univers, instant: Instant) -> None:
        bodies = [univers.trouver_corps(body_id) for body_id in self.body_ids]
        self.backend.synchroniser_vers_corps(bodies)
        for body in bodies:
            body.etat().instant = instant


@dataclass(slots=True)
class DomainePopulationSR:
    """Large flat-space SR population with an explicit hot force provider.

    The provider reads the array backend directly. It must return the physical
    coordinate three-force ``dp/dt`` for every row. Gravitational coupling is
    intentionally not invented here: if gravity becomes relevant for a fast
    vehicle, an explicit weak-field approximation or a transition to the GR
    path must be chosen by the scenario.
    """

    nom: str
    backend: ArrayStateBackend
    force_provider: ForceProviderSRHot = _forces_sr_nulles
    integrateur: IntegrateurPopulationSRTableau = field(default_factory=IntegrateurPopulationSRTableau)
    regime: RegimeDynamique = field(default=RegimeDynamique.RELATIVISTE_SPECIAL, init=False)

    def __post_init__(self) -> None:
        sr = np.ones(len(self.backend.body_ids), dtype=np.int8)
        if not np.array_equal(self.backend.regime_codes, sr):
            raise ValueError("SR hot domain accepts only special-relativistic array rows")

    @property
    def corps_ids(self) -> tuple[str, ...]:
        return self.backend.body_ids

    def avancer_hot(self, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        forces = np.asarray(self.force_provider(self.backend, instant), dtype=np.float64)
        self.integrateur.avancer_forces_constantes(self.backend, forces, dt_s)
        return []

    def synchroniser_objets(self, univers: Univers, instant: Instant) -> None:
        bodies = [univers.trouver_corps(body_id) for body_id in self.body_ids]
        self.backend.synchroniser_vers_corps(bodies)
        for body in bodies:
            body.etat().instant = instant


@dataclass(slots=True)
class SimulationGrandeEchelleMultiRegime:
    """Coordinate-time orchestrator whose hot domains stay in array form.

    This is complementary to :class:`SimulationMultiRegime`: the latter keeps
    physical Python objects authoritative and is ideal for small heterogeneous
    scenes; this class keeps large Newtonian/SR populations in contiguous
    arrays and synchronizes semantic objects only when explicitly requested.
    """

    instant_courant: Instant
    domaines: list[DomaineEvolutionGrandeEchelle] = field(default_factory=list)
    pas_effectues: int = 0
    historique_evenements: list[EvenementPhysique] = field(default_factory=list)
    _corps_enregistres: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        initial = list(self.domaines)
        self.domaines = []
        for domaine in initial:
            self.ajouter_domaine(domaine)

    def ajouter_domaine(self, domaine: DomaineEvolutionGrandeEchelle) -> None:
        ids = tuple(domaine.corps_ids)
        if not ids:
            raise ValueError("A large-scale dynamics domain must contain at least one body")
        if len(set(ids)) != len(ids):
            raise ValueError(f"Duplicate body ids inside domain {domaine.nom}")
        overlap = self._corps_enregistres.intersection(ids)
        if overlap:
            raise ValueError(f"Bodies already owned by another hot domain: {sorted(overlap)}")
        self._corps_enregistres.update(ids)
        self.domaines.append(domaine)

    def domaine(self, nom: str) -> DomaineEvolutionGrandeEchelle:
        for domaine in self.domaines:
            if domaine.nom == nom:
                return domaine
        raise KeyError(nom)

    def avancer(self, dt_s: float) -> list[EvenementPhysique]:
        dt = float(dt_s)
        if dt <= 0:
            raise ValueError("Time step must be positive")
        instant = self.instant_courant
        events: list[EvenementPhysique] = []
        for domaine in self.domaines:
            events.extend(domaine.avancer_hot(instant, dt))
        self.instant_courant = Instant(instant.seconds + dt)
        self.pas_effectues += 1
        self.historique_evenements.extend(events)
        return events

    def executer(self, duree_s: float, dt_s: float) -> None:
        duration = float(duree_s)
        step = float(dt_s)
        if duration < 0:
            raise ValueError("Duration must be non-negative")
        if step <= 0:
            raise ValueError("Time step must be positive")
        target = self.instant_courant.seconds + duration
        tolerance = max(1e-12, abs(target) * 1e-12)
        while self.instant_courant.seconds < target - tolerance:
            self.avancer(min(step, target - self.instant_courant.seconds))

    def synchroniser_objets(self, univers: Univers) -> None:
        """Explicit O(N) semantic synchronization barrier."""
        for domaine in self.domaines:
            domaine.synchroniser_objets(univers, self.instant_courant)

    def backends(self) -> tuple[ArrayStateBackend, ...]:
        result = []
        for domaine in self.domaines:
            backend = getattr(domaine, "backend", None)
            if backend is not None:
                result.append(backend)
        return tuple(result)
