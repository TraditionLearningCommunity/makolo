"""Hot array-backed orchestration for large multi-regime simulations.

Array domains keep large Newtonian/SR populations authoritative between
explicit synchronization barriers. Numerical ownership is dynamic: a body may
remain registered in an array backend while temporarily being evolved by a GR
object domain, but exactly one domain may participate in its evolution at any
instant.
"""
from __future__ import annotations

from collections import Counter
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

    @property
    def corps_participants(self) -> tuple[str, ...]: ...

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

    @property
    def corps_participants(self) -> tuple[str, ...]:
        mask = self.backend.masque_evolution()
        return tuple(body_id for body_id, enabled in zip(self.body_ids, mask) if enabled)

    def avancer_hot(self, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        self.integrateur.avancer(self.backend, dt_s)
        return []

    def synchroniser_objets(self, univers: Univers, instant: Instant) -> None:
        for body_id in self.corps_participants:
            body = univers.trouver_corps(body_id)
            self.backend.synchroniser_un_corps(body)
            body.etat().instant = instant


@dataclass(slots=True)
class DomainePopulationSR:
    """Large flat-space SR population with an explicit hot force provider.

    The provider must return the physical coordinate three-force ``dp/dt``.
    Gravity is not silently treated as Newtonian at relativistic speed. If
    curvature becomes relevant, the body must explicitly migrate to a GR path.
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

    @property
    def corps_participants(self) -> tuple[str, ...]:
        mask = self.backend.masque_evolution()
        return tuple(body_id for body_id, enabled in zip(self.body_ids, mask) if enabled)

    def avancer_hot(self, instant: Instant, dt_s: float) -> list[EvenementPhysique]:
        forces = np.asarray(self.force_provider(self.backend, instant), dtype=np.float64)
        self.integrateur.avancer_forces_constantes(self.backend, forces, dt_s)
        return []

    def synchroniser_objets(self, univers: Univers, instant: Instant) -> None:
        for body_id in self.corps_participants:
            body = univers.trouver_corps(body_id)
            self.backend.synchroniser_un_corps(body)
            body.etat().instant = instant


@dataclass(slots=True)
class SimulationGrandeEchelleMultiRegime:
    """Coordinate-time orchestrator for dynamic numerical ownership.

    Domain registries may overlap because a suspended array row can coexist
    with a materialized GR object. The invariant is stricter and dynamic:
    exactly zero or one domain may *participate* in the evolution of a body at
    a given instant; two simultaneous owners are rejected before the step.
    """

    instant_courant: Instant
    domaines: list[DomaineEvolutionGrandeEchelle] = field(default_factory=list)
    pas_effectues: int = 0
    historique_evenements: list[EvenementPhysique] = field(default_factory=list)

    def __post_init__(self) -> None:
        initial = list(self.domaines)
        self.domaines = []
        for domaine in initial:
            self.ajouter_domaine(domaine)
        self.verifier_propriete_unique()

    def ajouter_domaine(self, domaine: DomaineEvolutionGrandeEchelle) -> None:
        if any(existing.nom == domaine.nom for existing in self.domaines):
            raise ValueError(f"Duplicate large-scale dynamics domain name: {domaine.nom}")
        ids = tuple(domaine.corps_ids)
        if len(set(ids)) != len(ids):
            raise ValueError(f"Duplicate body ids inside domain {domaine.nom}")
        self.domaines.append(domaine)
        self.verifier_propriete_unique()

    def domaine(self, nom: str) -> DomaineEvolutionGrandeEchelle:
        for domaine in self.domaines:
            if domaine.nom == nom:
                return domaine
        raise KeyError(nom)

    def proprietaires(self) -> dict[str, str]:
        owners: dict[str, str] = {}
        for domain in self.domaines:
            for body_id in domain.corps_participants:
                if body_id in owners:
                    raise RuntimeError(
                        f"Body {body_id} is simultaneously evolved by {owners[body_id]} and {domain.nom}"
                    )
                owners[body_id] = domain.nom
        return owners

    def verifier_propriete_unique(self) -> None:
        counts = Counter(
            body_id
            for domain in self.domaines
            for body_id in domain.corps_participants
        )
        duplicates = sorted(body_id for body_id, count in counts.items() if count > 1)
        if duplicates:
            raise RuntimeError(f"Bodies have multiple active dynamics owners: {duplicates}")

    def avancer(self, dt_s: float) -> list[EvenementPhysique]:
        dt = float(dt_s)
        if dt <= 0:
            raise ValueError("Time step must be positive")
        self.verifier_propriete_unique()
        instant = self.instant_courant
        events: list[EvenementPhysique] = []
        for domaine in self.domaines:
            events.extend(domaine.avancer_hot(instant, dt))
        self.verifier_propriete_unique()
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
        """Explicit semantic synchronization barrier for current owners only."""
        self.verifier_propriete_unique()
        for domaine in self.domaines:
            domaine.synchroniser_objets(univers, self.instant_courant)

    def backends(self) -> tuple[ArrayStateBackend, ...]:
        result = []
        for domaine in self.domaines:
            backend = getattr(domaine, "backend", None)
            if isinstance(backend, ArrayStateBackend):
                result.append(backend)
        return tuple(result)
