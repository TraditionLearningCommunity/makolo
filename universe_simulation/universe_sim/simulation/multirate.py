"""Coordinate-time scheduling for multi-rate physical evolution."""
from __future__ import annotations

from dataclasses import dataclass, field
import heapq


@dataclass(frozen=True, slots=True)
class CadenceEvolution:
    nom: str
    pas_s: float
    phase_s: float = 0.0

    def __post_init__(self) -> None:
        if not self.nom:
            raise ValueError("Evolution cadence requires a name")
        if self.pas_s <= 0:
            raise ValueError("Evolution cadence must be positive")
        if self.phase_s < 0 or self.phase_s >= self.pas_s:
            raise ValueError("phase_s must satisfy 0 <= phase_s < pas_s")

    def premiere_echeance(self) -> float:
        return self.pas_s if self.phase_s == 0.0 else self.phase_s


@dataclass(frozen=True, slots=True)
class PasEvolution:
    nom: str
    dt_s: float
    pas_nominal_s: float
    partiel: bool = False


@dataclass(frozen=True, slots=True)
class EcheanceMultiTaux:
    offset_s: float
    evolutions: tuple[PasEvolution, ...]
    barriere_synchronisation: bool = False


@dataclass(slots=True)
class OrdonnanceurMultiTaux:
    """Build a shared coordinate-time schedule without hiding coupling choices.

    This object only plans when each evolution is due. It does not mutate
    physical states. A consumer that couples evolutions at different cadences
    must therefore provide an explicit prediction/interpolation policy for
    bodies that are queried between their committed updates.
    """

    cadences: dict[str, CadenceEvolution] = field(default_factory=dict)

    def ajouter(self, cadence: CadenceEvolution) -> None:
        if cadence.nom in self.cadences:
            raise ValueError(f"Duplicate evolution cadence: {cadence.nom}")
        self.cadences[cadence.nom] = cadence

    def planifier(self, duree_s: float) -> tuple[EcheanceMultiTaux, ...]:
        duration = float(duree_s)
        if duration < 0:
            raise ValueError("Duration must be non-negative")
        if duration == 0 or not self.cadences:
            return ()

        names = tuple(sorted(self.cadences))
        last = {name: 0.0 for name in names}
        heap: list[tuple[float, str]] = []
        for name in names:
            first = self.cadences[name].premiere_echeance()
            if first <= duration:
                heapq.heappush(heap, (first, name))

        buckets: list[tuple[float, list[PasEvolution]]] = []
        while heap:
            time, name = heapq.heappop(heap)
            tolerance = max(1e-12, abs(time) * 1e-12)
            due = [(time, name)]
            while heap and abs(heap[0][0] - time) <= tolerance:
                due.append(heapq.heappop(heap))

            steps: list[PasEvolution] = []
            for due_time, due_name in due:
                cadence = self.cadences[due_name]
                dt = due_time - last[due_name]
                steps.append(PasEvolution(due_name, dt, cadence.pas_s, False))
                last[due_name] = due_time
                next_time = due_time + cadence.pas_s
                if next_time <= duration + max(1e-12, abs(duration) * 1e-12):
                    heapq.heappush(heap, (min(next_time, duration), due_name))
            buckets.append((time, steps))

        final_steps: list[PasEvolution] = []
        for name in names:
            remaining = duration - last[name]
            tolerance = max(1e-12, abs(duration) * 1e-12)
            if remaining > tolerance:
                cadence = self.cadences[name]
                final_steps.append(PasEvolution(name, remaining, cadence.pas_s, True))

        if buckets and abs(buckets[-1][0] - duration) <= max(1e-12, abs(duration) * 1e-12):
            time, steps = buckets[-1]
            existing = {step.nom for step in steps}
            steps.extend(step for step in final_steps if step.nom not in existing)
            buckets[-1] = (duration, steps)
        elif final_steps:
            buckets.append((duration, final_steps))

        return tuple(
            EcheanceMultiTaux(
                offset,
                tuple(sorted(steps, key=lambda step: step.nom)),
                abs(offset - duration) <= max(1e-12, abs(duration) * 1e-12),
            )
            for offset, steps in buckets
        )
