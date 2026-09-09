"""Multi-rate coordinate-time execution for large hot numerical domains."""
from __future__ import annotations

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
    """Advance hot domains at distinct cadences on one coordinate-time axis.

    Domain states are only jointly simultaneous at synchronization barriers.
    Cross-domain coupling is therefore never guessed: an optional coupling
    policy is invoked before each deadline and is responsible for any required
    prediction/interpolation of lagging domains.
    """

    origine_temps: Instant
    domaines: list[DomaineEvolutionGrandeEchelle]
    cadences: dict[str, CadenceEvolution]
    politique_couplage: PolitiqueCouplageMultiTaux | None = None
    historique_evenements: list[EvenementPhysique] = field(default_factory=list)
    echeances_executees: int = 0
    _temps_domaines_s: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _corps_enregistres: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        names = [domain.nom for domain in self.domaines]
        if not names or len(set(names)) != len(names):
            raise ValueError("Multi-rate large-scale simulation requires unique non-empty domain names")
        if set(names) != set(self.cadences):
            raise ValueError("Every domain must have exactly one cadence")
        for domain in self.domaines:
            ids = tuple(domain.corps_ids)
            overlap = self._corps_enregistres.intersection(ids)
            if overlap:
                raise ValueError(f"Bodies already owned by another domain: {sorted(overlap)}")
            self._corps_enregistres.update(ids)
        self._temps_domaines_s = {name: self.origine_temps.seconds for name in names}

    def domaine(self, nom: str) -> DomaineEvolutionGrandeEchelle:
        for domain in self.domaines:
            if domain.nom == nom:
                return domain
        raise KeyError(nom)

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
            self.echeances_executees += 1

        if schedule and not self.simultanes(max(1e-9, abs(segment_origin + duration) * 1e-12)):
            raise RuntimeError("Final multi-rate synchronization barrier was not reached")

    def synchroniser_objets(self, univers: Univers) -> None:
        instant = self.instant_barriere
        for domain in self.domaines:
            domain.synchroniser_objets(univers, instant)
