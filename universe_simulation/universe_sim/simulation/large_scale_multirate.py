"""Multi-rate coordinate-time execution for large hot numerical domains."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from ..events import EvenementPhysique
from ..systems import Univers
from ..values import Instant
from .large_scale_engine import DomaineEvolutionGrandeEchelle
from .multirate import CadenceEvolution, EcheanceMultiTaux, OrdonnanceurMultiTaux


PolitiqueCouplageMultiTaux = Callable[["SimulationGrandeEchelleMultiTaux", EcheanceMultiTaux], None]


@dataclass(slots=True)
class SimulationGrandeEchelleMultiTaux:
    """Advance dynamically owned domains at distinct coordinate-time cadences.

    A body registry may appear in more than one domain, but only one domain may
    currently participate in its evolution. This enables SR-array -> GR-object
    migrations without removing immutable rows from large backends.
    """

    origine_temps: Instant
    domaines: list[DomaineEvolutionGrandeEchelle]
    cadences: dict[str, CadenceEvolution]
    politique_couplage: PolitiqueCouplageMultiTaux | None = None
    historique_evenements: list[EvenementPhysique] = field(default_factory=list)
    echeances_executees: int = 0
    _temps_domaines_s: dict[str, float] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        names = [domain.nom for domain in self.domaines]
        if not names or len(set(names)) != len(names):
            raise ValueError("Multi-rate large-scale simulation requires unique non-empty domain names")
        if set(names) != set(self.cadences):
            raise ValueError("Every domain must have exactly one cadence")
        for domain in self.domaines:
            if len(set(domain.corps_ids)) != len(domain.corps_ids):
                raise ValueError(f"Duplicate body ids inside domain {domain.nom}")
        self._temps_domaines_s = {name: self.origine_temps.seconds for name in names}
        self.verifier_propriete_unique()

    def domaine(self, nom: str) -> DomaineEvolutionGrandeEchelle:
        for domain in self.domaines:
            if domain.nom == nom:
                return domain
        raise KeyError(nom)

    def verifier_propriete_unique(self) -> None:
        counts = Counter(
            body_id
            for domain in self.domaines
            for body_id in domain.corps_participants
        )
        duplicates = sorted(body_id for body_id, count in counts.items() if count > 1)
        if duplicates:
            raise RuntimeError(f"Bodies have multiple active dynamics owners: {duplicates}")

    def temps_domaine(self, nom: str) -> Instant:
        return Instant(self._temps_domaines_s[nom])

    def simultanes(self, tolerance_s: float = 1e-9) -> bool:
        values = tuple(self._temps_domaines_s.values())
        return not values or max(values) - min(values) <= tolerance_s

    @property
    def instant_barriere(self) -> Instant:
        if not self.simultanes():
            raise RuntimeError("Hot domains are not at a common coordinate-time barrier")
        values = tuple(self._temps_domaines_s.values())
        return Instant(self.origine_temps.seconds if not values else values[0])

    def executer(self, duree_s: float) -> None:
        duration = float(duree_s)
        if duration < 0:
            raise ValueError("Duration must be non-negative")
        scheduler = OrdonnanceurMultiTaux(dict(self.cadences))
        schedule = scheduler.planifier(duration)
        start = min(self._temps_domaines_s.values(), default=self.origine_temps.seconds)
        if not self.simultanes():
            raise RuntimeError("A new multi-rate segment must start from a synchronization barrier")
        segment_origin = start

        for deadline in schedule:
            if self.politique_couplage is not None:
                self.politique_couplage(self, deadline)
            self.verifier_propriete_unique()
            for planned in deadline.evolutions:
                domain = self.domaine(planned.nom)
                current = self._temps_domaines_s[planned.nom]
                expected = segment_origin + deadline.offset_s
                events = domain.avancer_hot(Instant(current), planned.dt_s)
                current += planned.dt_s
                tolerance = max(1e-9, abs(expected) * 1e-12)
                if abs(current - expected) > tolerance:
                    raise RuntimeError(
                        f"Domain {planned.nom} ended at {current}, expected coordinate time {expected}"
                    )
                self._temps_domaines_s[planned.nom] = current
                self.historique_evenements.extend(events)
            self.verifier_propriete_unique()
            self.echeances_executees += 1

        if schedule and not self.simultanes(max(1e-9, abs(segment_origin + duration) * 1e-12)):
            raise RuntimeError("Final multi-rate synchronization barrier was not reached")

    def synchroniser_objets(self, univers: Univers) -> None:
        instant = self.instant_barriere
        self.verifier_propriete_unique()
        for domain in self.domaines:
            domain.synchroniser_objets(univers, instant)
